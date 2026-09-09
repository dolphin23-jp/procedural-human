from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base


QUALITY_TIERS = (
    {
        "name": "baseline",
        "minCircularity": 0.12,
        "minContrast": 8.0,
        "maxPriorDistance": 40.0,
        "maxArea": 350,
    },
    {
        "name": "moderate",
        "minCircularity": 0.30,
        "minContrast": 15.0,
        "maxPriorDistance": 35.0,
        "maxArea": 250,
    },
    {
        "name": "high",
        "minCircularity": 0.45,
        "minContrast": 22.0,
        "maxPriorDistance": 30.0,
        "maxArea": 200,
    },
    {
        "name": "very-high",
        "minCircularity": 0.55,
        "minContrast": 28.0,
        "maxPriorDistance": 25.0,
        "maxArea": 160,
    },
)


def _filtered(
    candidates_by_frame: list[list[base.Candidate]],
    tier: dict[str, object],
) -> list[list[base.Candidate]]:
    return [
        [
            candidate
            for candidate in candidates
            if candidate.circularity >= float(tier["minCircularity"])
            and candidate.contrast >= float(tier["minContrast"])
            and candidate.prior_distance <= float(tier["maxPriorDistance"])
            and candidate.area <= int(tier["maxArea"])
        ]
        for candidates in candidates_by_frame
    ]


def _path_nodes(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[base.Candidate]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for frame_index, candidate_index in path:
        candidate = candidates_by_frame[frame_index][candidate_index]
        rows.append(
            {
                "globalFrameIndex": frame_index,
                "sourceFilename": base._source_filename(frame_index),
                "centroidSourcePixels": {
                    "x": candidate.x,
                    "y": candidate.y,
                },
                "areaPixels": candidate.area,
                "circularity": candidate.circularity,
                "contrast": candidate.contrast,
                "priorDistanceSourcePixels": candidate.prior_distance,
                "meanRgb": {
                    "r": candidate.mean_r,
                    "g": candidate.mean_g,
                    "b": candidate.mean_b,
                },
            }
        )
    return rows


def _segment_path(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[base.Candidate]],
    *,
    max_gap: int = 3,
    max_jump_per_frame: float = 5.0,
) -> list[list[tuple[int, int]]]:
    if not path:
        return []

    segments: list[list[tuple[int, int]]] = []
    current = [path[0]]

    for current_key in path[1:]:
        previous_key = current[-1]
        previous = candidates_by_frame[previous_key[0]][previous_key[1]]
        candidate = candidates_by_frame[current_key[0]][current_key[1]]
        gap = current_key[0] - previous_key[0]
        jump = float(
            np.linalg.norm(
                np.asarray([candidate.x, candidate.y])
                - np.asarray([previous.x, previous.y])
            )
        )
        acceptable = (
            1 <= gap <= max_gap
            and jump / gap <= max_jump_per_frame
        )
        if acceptable:
            current.append(current_key)
        else:
            segments.append(current)
            current = [current_key]

    segments.append(current)
    return sorted(
        segments,
        key=lambda segment: (
            segment[-1][0] - segment[0][0] + 1,
            len(segment),
        ),
        reverse=True,
    )


def _metrics_json(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[base.Candidate]],
) -> dict[str, object] | None:
    metrics = base._track_metrics(path, candidates_by_frame)
    if metrics is None:
        return None
    return base._metrics_json(metrics)


def _segment_summaries(
    path: list[tuple[int, int]],
    candidates_by_frame: list[list[base.Candidate]],
) -> list[dict[str, object]]:
    segments = _segment_path(path, candidates_by_frame)
    result: list[dict[str, object]] = []
    for index, segment in enumerate(segments[:8], start=1):
        metrics = _metrics_json(segment, candidates_by_frame)
        if metrics is None:
            continue
        result.append(
            {
                "rank": index,
                "metrics": metrics,
                "nodeCount": len(segment),
                "firstNode": _path_nodes(
                    [segment[0]],
                    candidates_by_frame,
                )[0],
                "lastNode": _path_nodes(
                    [segment[-1]],
                    candidates_by_frame,
                )[0],
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bone-report", type=Path, required=True)
    parser.add_argument("--atlas-root", type=Path, required=True)
    parser.add_argument("--cryo-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    bone_report = json.loads(
        args.bone_report.read_text(encoding="utf-8")
    )
    bone_tracks = base._bone_tracks(bone_report)
    atlas = {
        label: base._read_ascii_ply_vertices(
            args.atlas_root / f"{label}.ply"
        )
        for label in (
            "radius",
            "ulna",
            *base.VESSELS,
        )
    }

    (
        proximal_z,
        distal_z,
        orientation,
        priors,
        diagnostics,
    ) = base._optimize_local_pair_prior(
        args.cryo_root,
        atlas,
        bone_tracks,
    )

    raw_candidates: list[list[base.Candidate]] = []
    for global_index in range(base.FRAME_COUNT):
        image = np.asarray(
            Image.open(
                args.cryo_root
                / base._source_filename(global_index)
            ).convert("RGB")
        )
        raw_candidates.append(
            base._extract_candidates(
                image,
                priors["radial_artery"][global_index],
            )
        )

    tier_results: list[dict[str, object]] = []
    for tier in QUALITY_TIERS:
        candidates = _filtered(raw_candidates, tier)
        path = base._best_track(candidates)
        metrics = _metrics_json(path, candidates)
        tier_results.append(
            {
                "tier": tier,
                "framesWithCandidate": int(
                    sum(bool(frame) for frame in candidates)
                ),
                "candidateCount": int(
                    sum(len(frame) for frame in candidates)
                ),
                "trackMetrics": metrics,
                "pathNodes": _path_nodes(path, candidates),
                "strictSegments": _segment_summaries(
                    path,
                    candidates,
                ),
            }
        )

    report = {
        "schema": "ph-a06-radial-source-refinement-diagnostic.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "anatomicalId": "structure.radial_artery.left",
        "coordinateSpace": {
            "kind": "source-image-stack",
            "patientSpaceClaim": False,
        },
        "registration": {
            "method": (
                "slice-local radius-ulna pair atlas prior "
                "with VHP source-image candidate extraction"
            ),
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "atlasGeometryUsedAsSubjectGeometry": False,
            "atlasPriorTissueSupport": diagnostics["radial_artery"],
        },
        "tiers": tier_results,
        "disposition": {
            "radialArteryRepresentationEstablished": False,
            "maskGenerationAllowed": False,
            "reason": (
                "diagnostic refinement only; a bounded source-supported "
                "segment must meet explicit continuity and image-quality "
                "thresholds before radial artery masks are accepted"
            ),
        },
        "claims": {
            "humanEdited": False,
            "anatomicallyReviewed": False,
            "medicalValidation": False,
            "completeVesselExtent": False,
            "patientSpaceGeometry": False,
            "automaticPromotionAllowed": False,
        },
    }

    args.output_root.mkdir(parents=True, exist_ok=True)
    (
        args.output_root
        / "a06-radial-source-refinement-diagnostic.v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "registration": report["registration"],
                "tiers": [
                    {
                        "tier": item["tier"],
                        "framesWithCandidate": item["framesWithCandidate"],
                        "candidateCount": item["candidateCount"],
                        "trackMetrics": item["trackMetrics"],
                        "strictSegments": item["strictSegments"][:3],
                    }
                    for item in tier_results
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
