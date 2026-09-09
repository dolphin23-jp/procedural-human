from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image


EXPECTED_WIDTH = 550
EXPECTED_HEIGHT = 750
EXPECTED_FRAME_COUNT = 451
SOURCE_WEBP_QUALITY = 72
SOURCE_WEBP_METHOD = 3


class ReviewAssetBuildError(RuntimeError):
    pass


def expected_frame_names() -> tuple[str, ...]:
    names: list[str] = []
    for position in range(1567, 1717):
        for suffix in ("a", "b", "c"):
            names.append(f"avf{position:04d}{suffix}.png")
    names.append("avf1717a.png")
    if len(names) != EXPECTED_FRAME_COUNT:
        raise AssertionError("unexpected bounded source frame count")
    return tuple(names)


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ReviewAssetBuildError(f"{path} root must be an object")
    return raw


def verify_source_stack(
    source_root: Path,
    source_verification: dict[str, Any],
) -> tuple[tuple[str, ...], str]:
    expected = expected_frame_names()
    actual = tuple(sorted(path.name for path in source_root.glob("avf*.png")))
    if set(actual) != set(expected) or len(actual) != EXPECTED_FRAME_COUNT:
        raise ReviewAssetBuildError(
            "source stack must contain exactly the 451 bounded source PNGs"
        )

    acquisition = source_verification.get("acquisition")
    if not isinstance(acquisition, dict):
        raise ReviewAssetBuildError("source verification has no acquisition")
    expected_aggregate = acquisition.get("cropFilenameShaAggregate")
    if not isinstance(expected_aggregate, str) or len(expected_aggregate) != 64:
        raise ReviewAssetBuildError(
            "source verification has invalid cropFilenameShaAggregate"
        )

    aggregate = sha256()
    for filename in expected:
        path = source_root / filename
        with Image.open(path) as image:
            if image.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                raise ReviewAssetBuildError(
                    f"unexpected source dimensions for {filename}: {image.size}"
                )
        digest = sha256_path(path)
        aggregate.update(filename.encode("utf-8"))
        aggregate.update(digest.encode("ascii"))

    actual_aggregate = aggregate.hexdigest()
    if actual_aggregate != expected_aggregate:
        raise ReviewAssetBuildError(
            "source crop aggregate mismatch: "
            f"expected {expected_aggregate}, got {actual_aggregate}"
        )
    return expected, actual_aggregate


def structure_support(
    manual_status: dict[str, Any],
) -> dict[str, str]:
    rows = manual_status.get("structures")
    if not isinstance(rows, list):
        raise ReviewAssetBuildError("manual status has no structures array")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = row.get("draftLabel")
        reason = row.get("reason")
        if isinstance(label, str) and isinstance(reason, str):
            result[label] = reason
    return result


def candidate_digests(manual_status: dict[str, Any]) -> list[str]:
    source = manual_status.get("source")
    if not isinstance(source, dict):
        raise ReviewAssetBuildError("manual status has no source object")
    digests: list[str] = []

    primary = source.get("candidateOutputDigest")
    if not isinstance(primary, str) or not primary.startswith("sha256:"):
        raise ReviewAssetBuildError("manual status has invalid candidateOutputDigest")
    digests.append(primary)

    supplemental = source.get("supplementalCandidateOutputs")
    if not isinstance(supplemental, list):
        raise ReviewAssetBuildError(
            "manual status has no supplementalCandidateOutputs"
        )
    for row in supplemental:
        if not isinstance(row, dict):
            continue
        digest = row.get("digest")
        if isinstance(digest, str) and digest.startswith("sha256:"):
            digests.append(digest)

    return sorted(set(digests))


def verify_mask_set(
    root: Path,
    label: str,
    expected_filenames: tuple[str, ...],
) -> Path:
    mask_root = root / "masks" / label
    if not mask_root.is_dir():
        raise ReviewAssetBuildError(f"missing mask directory: {mask_root}")

    expected = set(expected_filenames)
    actual = {path.with_suffix(".png").name for path in mask_root.glob("*.pgm")}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ReviewAssetBuildError(
            f"{label} mask support mismatch; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    return mask_root


def binary_mask_to_png(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        grayscale = image.convert("L")
        if grayscale.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
            raise ReviewAssetBuildError(
                f"unexpected mask dimensions for {source}: {grayscale.size}"
            )
        histogram = grayscale.histogram()
        nonzero_bins = [index for index, count in enumerate(histogram) if count]
        if any(value not in (0, 255) for value in nonzero_bins):
            raise ReviewAssetBuildError(
                f"mask is not binary 0/255 data: {source}"
            )
        binary = grayscale.convert("1", dither=Image.Dither.NONE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        binary.save(destination, format="PNG", optimize=False, compress_level=3)


def source_to_webp(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        destination.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(
            destination,
            format="WEBP",
            quality=SOURCE_WEBP_QUALITY,
            method=SOURCE_WEBP_METHOD,
        )


def build_review_assets(
    *,
    source_root: Path,
    a05_root: Path,
    bones_root: Path,
    ulnar_root: Path,
    source_verification_path: Path,
    manual_status_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    source_verification = load_json(source_verification_path)
    manual_status = load_json(manual_status_path)
    source_filenames, crop_aggregate = verify_source_stack(
        source_root,
        source_verification,
    )
    support_text = structure_support(manual_status)

    structures = [
        {
            "draftLabel": "skin",
            "displayName": "Skin",
            "root": a05_root,
            "filenames": source_filenames,
            "sourceClass": "algorithm-derived V0 candidate",
        },
        {
            "draftLabel": "subcutaneous_soft_tissue",
            "displayName": "Subcutaneous soft tissue",
            "root": a05_root,
            "filenames": source_filenames,
            "sourceClass": "algorithm-derived V0 candidate",
        },
        {
            "draftLabel": "major_muscle_tendon_region",
            "displayName": "Major muscle / tendon region",
            "root": a05_root,
            "filenames": source_filenames,
            "sourceClass": "algorithm-derived V0 candidate",
        },
        {
            "draftLabel": "radius",
            "displayName": "Radius",
            "root": bones_root,
            "filenames": source_filenames[:357],
            "sourceClass": "algorithm-derived V0 candidate; same-cadaver CT corroboration",
        },
        {
            "draftLabel": "ulna",
            "displayName": "Ulna",
            "root": bones_root,
            "filenames": source_filenames[:357],
            "sourceClass": "algorithm-derived V0 candidate; same-cadaver CT corroboration",
        },
        {
            "draftLabel": "ulnar_artery",
            "displayName": "Ulnar artery",
            "root": ulnar_root,
            "filenames": source_filenames[237:343],
            "sourceClass": "algorithm-derived bounded continuous V0 candidate",
        },
    ]

    if output_root.exists():
        shutil.rmtree(output_root)
    (output_root / "source").mkdir(parents=True)
    (output_root / "masks").mkdir(parents=True)

    for filename in source_filenames:
        source_to_webp(
            source_root / filename,
            output_root / "source" / (Path(filename).stem + ".webp"),
        )

    manifest_structures: list[dict[str, Any]] = []
    for structure in structures:
        label = structure["draftLabel"]
        filenames = structure["filenames"]
        assert isinstance(label, str)
        assert isinstance(filenames, tuple)
        mask_root = verify_mask_set(
            structure["root"],
            label,
            filenames,
        )
        for filename in filenames:
            binary_mask_to_png(
                mask_root / (Path(filename).stem + ".pgm"),
                output_root / "masks" / label / filename,
            )
        manifest_structures.append(
            {
                "draftLabel": label,
                "displayName": structure["displayName"],
                "sourceClass": structure["sourceClass"],
                "supportStatus": support_text.get(label, "support description unavailable"),
                "supportedFrameCount": len(filenames),
                "firstSourceFilename": filenames[0],
                "lastSourceFilename": filenames[-1],
                "maskPathPrefix": f"masks/{label}/",
            }
        )

    revision = sha256()
    revision.update(b"ph-a06-ipad-review-data.v1\0")
    revision.update(crop_aggregate.encode("ascii"))
    for digest in candidate_digests(manual_status):
        revision.update(b"\0")
        revision.update(digest.encode("ascii"))
    asset_revision = "sha256:" + revision.hexdigest()

    manifest = {
        "schema": "ph-a06-ipad-review-data.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "assetRevision": asset_revision,
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "source": {
            "dataset": "U.S. National Library of Medicine — Visible Human Project — Visible Human Female",
            "sourceClass": "cadaver-derived",
            "frameCount": EXPECTED_FRAME_COUNT,
            "firstSourceFilename": source_filenames[0],
            "lastSourceFilename": source_filenames[-1],
            "cropDimensionsPixels": {
                "width": EXPECTED_WIDTH,
                "height": EXPECTED_HEIGHT,
            },
            "cropFilenameShaAggregate": "sha256:" + crop_aggregate,
            "imageFormat": "webp",
            "imagePathPrefix": "source/",
            "derivedReviewImageQuality": SOURCE_WEBP_QUALITY,
        },
        "structures": manifest_structures,
        "distribution": {
            "sourceSnapshotRecordedAt": source_verification.get("recordedAt"),
            "attribution": "Courtesy of the U.S. National Library of Medicine",
            "noEndorsement": "NLM does not endorse Procedural Human.",
            "currencyNotice": (
                "This review package is derived from the recorded 2026 Visible Human "
                "source snapshot and may not reflect the most current or accurate NLM data."
            ),
            "reviewPurposeOnly": True,
        },
        "claims": {
            "humanReviewRecorded": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "patientSpaceGeometry": False,
            "medicalMaster": False,
            "runtimeAsset": False,
            "automaticPromotionAllowed": False,
        },
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build transient, source-space-only TASK-A06 iPad review assets."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--a05-root", type=Path, required=True)
    parser.add_argument("--bones-root", type=Path, required=True)
    parser.add_argument("--ulnar-root", type=Path, required=True)
    parser.add_argument("--source-verification", type=Path, required=True)
    parser.add_argument("--manual-status", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    manifest = build_review_assets(
        source_root=args.source_root,
        a05_root=args.a05_root,
        bones_root=args.bones_root,
        ulnar_root=args.ulnar_root,
        source_verification_path=args.source_verification,
        manual_status_path=args.manual_status,
        output_root=args.output_root,
    )
    print(
        json.dumps(
            {
                "assetRevision": manifest["assetRevision"],
                "sourceFrameCount": manifest["source"]["frameCount"],
                "structureCount": len(manifest["structures"]),
                "medicalValidation": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
