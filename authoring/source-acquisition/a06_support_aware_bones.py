from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


START_NOMINAL_INDEX = 1567
STOP_NOMINAL_INDEX = 1685
FIRST_GLOBAL_FRAME = 0
LAST_GLOBAL_FRAME = (STOP_NOMINAL_INDEX - START_NOMINAL_INDEX) * 3 + 2

CT_STORED_BONE_THRESHOLD = 1300
CT_MIN_COMPONENT_PIXELS = 50
CRYO_SEARCH_RADIUS_PIXELS = 40
CRYO_MIN_COMPONENT_PIXELS = 700
CRYO_FALLBACK_RULES = (
    (140.0, 115, 145),
    (135.0, 135, 135),
    (125.0, 150, 120),
)

INITIAL_CRYO_SEEDS = {
    "radius": (337.0, 151.0),
    "ulna": (306.0, 255.0),
}


class MultimodalityBoneError(RuntimeError):
    pass


@dataclass(frozen=True)
class Component:
    area: int
    x: float
    y: float
    label: int


def _frame_sequence() -> list[str]:
    names: list[str] = []
    for position in range(1567, 1717):
        for suffix in ("a", "b", "c"):
            names.append(f"avf{position:04d}{suffix}.png")
    names.append("avf1717a.png")
    if len(names) != 451:
        raise AssertionError("unexpected A05 frame count")
    return names


def _sha256_path(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_pgm(path: Path, mask: np.ndarray) -> str:
    if mask.dtype != np.uint8 or mask.ndim != 2:
        raise MultimodalityBoneError("mask must be uint8 HxW")
    payload = (mask > 0).astype(np.uint8) * 255
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"P5\n{payload.shape[1]} {payload.shape[0]}\n255\n".encode("ascii")
    path.write_bytes(header + payload.tobytes())
    return _sha256_path(path)


def _ct_candidates(image: np.ndarray) -> list[Component]:
    mask = (image >= CT_STORED_BONE_THRESHOLD).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    result: list[Component] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        x, y = map(float, centroids[label])
        if (
            area >= CT_MIN_COMPONENT_PIXELS
            and x > 400.0
            and 120.0 < y < 320.0
        ):
            result.append(Component(area=area, x=x, y=y, label=label))
    return result


def _track_ct_bones(ct_root: Path) -> dict[str, dict[int, Component]]:
    first = _ct_candidates(
        np.asarray(Image.open(ct_root / f"cvf{START_NOMINAL_INDEX:04d}f.png"))
    )
    if len(first) < 2:
        raise MultimodalityBoneError("initial CT slice does not contain two forearm-bone candidates")
    first = sorted(first, key=lambda item: item.x)
    # The VHP CT header states that the right-hand image side corresponds to the
    # subject's left side. The lateral member of the left forearm pair is radius.
    current = {
        "radius": first[-1],
        "ulna": first[-2],
    }
    velocity = {
        "radius": np.zeros(2, dtype=float),
        "ulna": np.zeros(2, dtype=float),
    }
    tracks: dict[str, dict[int, Component]] = {"radius": {}, "ulna": {}}

    for nominal_index in range(START_NOMINAL_INDEX, STOP_NOMINAL_INDEX + 1):
        candidates = _ct_candidates(
            np.asarray(Image.open(ct_root / f"cvf{nominal_index:04d}f.png"))
        )
        if nominal_index == START_NOMINAL_INDEX:
            chosen = current.copy()
        else:
            predictions = {
                key: np.array([current[key].x, current[key].y]) + velocity[key]
                for key in current
            }
            best: tuple[float, Component, Component] | None = None
            for radius in candidates:
                for ulna in candidates:
                    if radius.label == ulna.label:
                        continue
                    cost = float(
                        np.linalg.norm(
                            np.array([radius.x, radius.y]) - predictions["radius"]
                        )
                        + np.linalg.norm(
                            np.array([ulna.x, ulna.y]) - predictions["ulna"]
                        )
                    )
                    if radius.x < ulna.x:
                        cost += 10.0
                    if best is None or cost < best[0]:
                        best = (cost, radius, ulna)
            if best is None:
                raise MultimodalityBoneError(
                    f"CT radius/ulna tracking failed at {nominal_index}"
                )
            chosen = {"radius": best[1], "ulna": best[2]}

        for key in ("radius", "ulna"):
            new = chosen[key]
            if nominal_index != START_NOMINAL_INDEX:
                old = np.array([current[key].x, current[key].y])
                delta = np.array([new.x, new.y]) - old
                velocity[key] = velocity[key] * 0.5 + delta * 0.5
            current[key] = new
            tracks[key][nominal_index] = new

        separation = hypot(
            chosen["radius"].x - chosen["ulna"].x,
            chosen["radius"].y - chosen["ulna"].y,
        )
        if separation < 10.0:
            raise MultimodalityBoneError(
                f"CT radius/ulna candidates collapse at {nominal_index}"
            )
    return tracks


def _candidate_mask(image: np.ndarray, rule: tuple[float, int, int]) -> np.ndarray:
    brightness_min, saturation_max, r_min = rule
    rgb = image.astype(np.int16)
    brightness = rgb.mean(axis=2)
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    return (
        (brightness >= brightness_min)
        & (saturation <= saturation_max)
        & (rgb[:, :, 0] >= r_min)
    ).astype(np.uint8)


def _local_component(
    image: np.ndarray,
    prediction: np.ndarray,
) -> tuple[np.ndarray, Component, int]:
    height, width = image.shape[:2]
    xx, yy = np.meshgrid(np.arange(width), np.arange(height))
    disk = (
        (xx - prediction[0]) ** 2 + (yy - prediction[1]) ** 2
        <= CRYO_SEARCH_RADIUS_PIXELS**2
    )

    for rule_index, rule in enumerate(CRYO_FALLBACK_RULES):
        local = _candidate_mask(image, rule)
        local[~disk] = 0
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(local, 8)
        options: list[tuple[float, int, int]] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 5:
                continue
            x, y = centroids[label]
            distance = hypot(float(x) - prediction[0], float(y) - prediction[1])
            score = distance - min(area, 2000) / 600.0
            options.append((score, -area, label))
        if not options:
            continue
        _, _, label = min(options)
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < CRYO_MIN_COMPONENT_PIXELS and rule_index < len(CRYO_FALLBACK_RULES) - 1:
            continue
        x, y = map(float, centroids[label])
        return (
            (labels == label).astype(np.uint8),
            Component(area=area, x=x, y=y, label=label),
            rule_index,
        )

    raise MultimodalityBoneError(
        f"no cryosection bone component near prediction {prediction.tolist()}"
    )


def _track_cryo_a_slices(
    cryo_root: Path,
) -> tuple[dict[str, dict[int, Component]], dict[str, dict[int, int]]]:
    tracks: dict[str, dict[int, Component]] = {"radius": {}, "ulna": {}}
    rules: dict[str, dict[int, int]] = {"radius": {}, "ulna": {}}
    current = {
        key: np.array(value, dtype=float)
        for key, value in INITIAL_CRYO_SEEDS.items()
    }
    velocity = {
        "radius": np.zeros(2, dtype=float),
        "ulna": np.zeros(2, dtype=float),
    }

    for nominal_index in range(START_NOMINAL_INDEX, STOP_NOMINAL_INDEX + 1):
        image = np.asarray(
            Image.open(cryo_root / f"avf{nominal_index:04d}a.png").convert("RGB")
        )
        chosen: dict[str, Component] = {}
        for key in ("radius", "ulna"):
            prediction = current[key] if nominal_index == START_NOMINAL_INDEX else current[key] + velocity[key]
            _, component, rule_index = _local_component(image, prediction)
            chosen[key] = component
            rules[key][nominal_index] = rule_index

        separation = hypot(
            chosen["radius"].x - chosen["ulna"].x,
            chosen["radius"].y - chosen["ulna"].y,
        )
        if separation < 25.0:
            raise MultimodalityBoneError(
                f"cryosection radius/ulna candidates are not separable at {nominal_index}"
            )

        for key in ("radius", "ulna"):
            new = np.array([chosen[key].x, chosen[key].y])
            if nominal_index != START_NOMINAL_INDEX:
                delta = new - current[key]
                velocity[key] = velocity[key] * 0.6 + delta * 0.4
            current[key] = new
            tracks[key][nominal_index] = chosen[key]
    return tracks, rules


def _fit_affine(
    ct_tracks: dict[str, dict[int, Component]],
    cryo_tracks: dict[str, dict[int, Component]],
    *,
    swapped: bool,
) -> tuple[np.ndarray, np.ndarray]:
    source: list[list[float]] = []
    target: list[list[float]] = []
    for nominal_index in range(START_NOMINAL_INDEX, STOP_NOMINAL_INDEX + 1):
        for key in ("radius", "ulna"):
            ct = ct_tracks[key][nominal_index]
            cryo_key = ("ulna" if key == "radius" else "radius") if swapped else key
            cryo = cryo_tracks[cryo_key][nominal_index]
            source.append([ct.x, ct.y, 1.0])
            target.append([cryo.x, cryo.y])
    x = np.asarray(source, dtype=float)
    y = np.asarray(target, dtype=float)
    transform, *_ = np.linalg.lstsq(x, y, rcond=None)
    residual = np.sqrt(((x @ transform - y) ** 2).sum(axis=1))
    return transform, residual


def _global_frame_index(nominal_index: int, suffix: str) -> int:
    suffix_offset = {"a": 0, "b": 1, "c": 2}[suffix]
    return (nominal_index - START_NOMINAL_INDEX) * 3 + suffix_offset


def _interpolate_anchor(
    track: dict[int, Component],
    nominal_index: int,
    suffix: str,
) -> np.ndarray:
    base = track[nominal_index]
    if suffix == "a" or nominal_index == STOP_NOMINAL_INDEX:
        return np.array([base.x, base.y], dtype=float)
    right = track[nominal_index + 1]
    fraction = {"b": 1.0 / 3.0, "c": 2.0 / 3.0}[suffix]
    return np.array(
        [
            base.x + (right.x - base.x) * fraction,
            base.y + (right.y - base.y) * fraction,
        ],
        dtype=float,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cryo-root", type=Path, required=True)
    parser.add_argument("--ct-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    frames = _frame_sequence()
    ct_tracks = _track_ct_bones(args.ct_root)
    cryo_tracks, cryo_rule_indices = _track_cryo_a_slices(args.cryo_root)

    direct_transform, direct_residual = _fit_affine(
        ct_tracks, cryo_tracks, swapped=False
    )
    _, swapped_residual = _fit_affine(ct_tracks, cryo_tracks, swapped=True)
    direct_mean = float(direct_residual.mean())
    swapped_mean = float(swapped_residual.mean())
    if not direct_mean < swapped_mean * 0.35:
        raise MultimodalityBoneError(
            "same-cadaver CT does not clearly corroborate radius/ulna identity assignment"
        )

    output_rows: dict[str, list[dict[str, object]]] = {"radius": [], "ulna": []}
    coverage: dict[str, list[int]] = {"radius": [], "ulna": []}
    ambiguity_rows: list[dict[str, object]] = []

    for nominal_index in range(START_NOMINAL_INDEX, STOP_NOMINAL_INDEX + 1):
        suffixes = ("a", "b", "c")
        for suffix in suffixes:
            global_index = _global_frame_index(nominal_index, suffix)
            filename = f"avf{nominal_index:04d}{suffix}.png"
            image = np.asarray(Image.open(args.cryo_root / filename).convert("RGB"))
            masks: dict[str, np.ndarray] = {}
            for key in ("radius", "ulna"):
                prediction = _interpolate_anchor(cryo_tracks[key], nominal_index, suffix)
                mask, component, rule_index = _local_component(image, prediction)
                if component.area < CRYO_MIN_COMPONENT_PIXELS:
                    raise MultimodalityBoneError(
                        f"{key} candidate is too small at {filename}: {component.area}"
                    )
                masks[key] = mask
                target = args.output_root / "masks" / key / f"{Path(filename).stem}.pgm"
                digest = _write_pgm(target, mask)
                coverage[key].append(component.area)
                output_rows[key].append(
                    {
                        "globalFrameIndex": global_index,
                        "sourceFilename": filename,
                        "candidatePixels": component.area,
                        "centroidSourcePixels": {
                            "x": component.x,
                            "y": component.y,
                        },
                        "anchorSourcePixels": {
                            "x": float(prediction[0]),
                            "y": float(prediction[1]),
                        },
                        "appearanceRuleIndex": rule_index,
                        "maskPath": str(target.relative_to(args.output_root)),
                        "maskSha256": digest,
                    }
                )
            overlap = int((masks["radius"] & masks["ulna"]).sum())
            if overlap:
                ambiguity_rows.append(
                    {
                        "globalFrameIndex": global_index,
                        "sourceFilename": filename,
                        "kind": "radius-ulna-overlap",
                        "overlapPixels": overlap,
                    }
                )

    if ambiguity_rows:
        raise MultimodalityBoneError(
            f"radius/ulna candidate masks overlap on {len(ambiguity_rows)} supported frames"
        )

    source_support_frame_count = LAST_GLOBAL_FRAME - FIRST_GLOBAL_FRAME + 1
    if any(len(rows) != source_support_frame_count for rows in output_rows.values()):
        raise MultimodalityBoneError("supported candidate frame count mismatch")

    report = {
        "schema": "ph-a06-multimodality-bone-candidate-report.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "pipelineProfile": "vhp-female-same-cadaver-ct-support-aware-bones-v0",
        "status": {
            "validationLevel": "V0",
            "reviewStatus": "unreviewed",
            "candidateOnly": True,
        },
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
            "ctRegistrationEstablished": False,
        },
        "support": {
            "meaning": "candidate-generation support for this pass; outside the interval is unknown, not anatomical absence",
            "firstGlobalFrameIndex": FIRST_GLOBAL_FRAME,
            "lastGlobalFrameIndex": LAST_GLOBAL_FRAME,
            "firstSourceFilename": frames[FIRST_GLOBAL_FRAME],
            "lastSourceFilename": frames[LAST_GLOBAL_FRAME],
            "supportedFrameCount": source_support_frame_count,
            "outsideSupportDisposition": "not-supported-by-this-pass",
        },
        "sameCadaverCtEvidence": {
            "nominalIndexStart": START_NOMINAL_INDEX,
            "nominalIndexStop": STOP_NOMINAL_INDEX,
            "ctBoneThresholdStoredValue": CT_STORED_BONE_THRESHOLD,
            "identityAssignment": {
                "radius": "lateral member of left forearm CT pair",
                "ulna": "medial member of left forearm CT pair",
            },
            "affineCorroboration": {
                "directMeanResidualPixels": direct_mean,
                "directMedianResidualPixels": float(np.median(direct_residual)),
                "swappedMeanResidualPixels": swapped_mean,
                "swappedMedianResidualPixels": float(np.median(swapped_residual)),
                "directToSwappedMeanRatio": direct_mean / swapped_mean,
                "directAssignmentClearlyPreferred": True,
                "transformCtPixelsToCryosectionCropPixels": direct_transform.tolist(),
            },
        },
        "structures": [
            {
                "draftLabel": key,
                "semanticId": f"structure.{key}.left",
                "representationStatus": "partial-support-v0-candidate",
                "supportedFrameCount": len(output_rows[key]),
                "minCandidatePixelsPerSupportedFrame": min(coverage[key]),
                "maxCandidatePixelsPerSupportedFrame": max(coverage[key]),
                "meanCandidatePixelsPerSupportedFrame": sum(coverage[key]) / len(coverage[key]),
                "files": output_rows[key],
            }
            for key in ("radius", "ulna")
        ],
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeStructureExtent": False,
            "patientSpaceGeometry": False,
            "ctRegistrationEstablished": False,
            "atlasGeometryUsedAsSubjectGeometry": False,
            "automaticPromotionAllowed": False,
        },
        "software": {
            "numpyVersion": np.__version__,
            "opencvVersion": cv2.__version__,
            "pillowVersion": Image.__version__ if hasattr(Image, "__version__") else None,
        },
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "a06-multimodality-bone-candidate-report.v0.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "supportedFrames": source_support_frame_count,
                "radiusMinPixels": min(coverage["radius"]),
                "ulnaMinPixels": min(coverage["ulna"]),
                "directMeanResidualPixels": direct_mean,
                "swappedMeanResidualPixels": swapped_mean,
                "directToSwappedMeanRatio": direct_mean / swapped_mean,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
