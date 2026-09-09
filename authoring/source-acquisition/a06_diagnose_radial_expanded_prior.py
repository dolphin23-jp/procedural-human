from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import a06_detect_vessel_candidates as base
import a06_diagnose_radial_bounded_segments as strict


SEARCH_RADII = (60, 80, 100)


def _run_radius(
    radius: int,
    cryo_root: Path,
    priors: dict[str, np.ndarray],
) -> dict[str, object]:
    original_radius = base.SEARCH_RADIUS
    base.SEARCH_RADIUS = radius
    try:
        candidates_by_frame: list[list[base.Candidate]] = []
        eligible_counts: list[int] = []
        for global_index in range(base.FRAME_COUNT):
            image = np.asarray(
                Image.open(
                    cryo_root / base._source_filename(global_index)
                ).convert("RGB")
            )
            candidates = base._extract_candidates(
                image,
                priors["radial_artery"][global_index],
            )
            candidates_by_frame.append(candidates)
            eligible_counts.append(
                sum(strict._eligible(candidate) for candidate in candidates)
            )

        path = strict._best_strict_path(candidates_by_frame)
        windows = strict._scan_windows(path, candidates_by_frame)
        whole = (
            strict._window_metrics(
                path,
                candidates_by_frame,
                0,
                len(path) - 1,
            )
            if path
            else None
        )
        return {
            "searchRadiusSourcePixels": radius,
            "candidateAvailability": {
                "framesWithAnyExtractedCandidate": int(
                    sum(bool(frame) for frame in candidates_by_frame)
                ),
                "framesWithAnyFixedQualityCandidate": int(
                    sum(count > 0 for count in eligible_counts)
                ),
                "totalFixedQualityCandidates": int(sum(eligible_counts)),
            },
            "bestStrictPath": (
                strict._metrics_json(whole)
                if whole is not None
                else None
            ),
            "acceptedSegmentCount": len(windows),
            "topAcceptedSegments": [
                strict._metrics_json(window)
                for window in windows[:10]
            ],
        }
    finally:
        base.SEARCH_RADIUS = original_radius


def _interval(row: dict[str, object]) -> tuple[int, int]:
    return (
        int(row["firstGlobalFrameIndex"]),
        int(row["lastGlobalFrameIndex"]),
    )


def _pairwise_reproducibility(
    runs: list[dict[str, object]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for left_index in range(len(runs)):
        for right_index in range(left_index + 1, len(runs)):
            left = runs[left_index]
            right = runs[right_index]
            left_segments = left["topAcceptedSegments"]
            right_segments = right["topAcceptedSegments"]
            if not left_segments or not right_segments:
                output.append(
                    {
                        "leftSearchRadiusSourcePixels": left[
                            "searchRadiusSourcePixels"
                        ],
                        "rightSearchRadiusSourcePixels": right[
                            "searchRadiusSourcePixels"
                        ],
                        "overlapFrames": 0,
                        "overlapFractionOfShorterTopSegment": 0.0,
                    }
                )
                continue

            left_interval = _interval(left_segments[0])
            right_interval = _interval(right_segments[0])
            overlap_start = max(left_interval[0], right_interval[0])
            overlap_end = min(left_interval[1], right_interval[1])
            overlap = max(0, overlap_end - overlap_start + 1)
            shorter = min(
                left_interval[1] - left_interval[0] + 1,
                right_interval[1] - right_interval[0] + 1,
            )
            output.append(
                {
                    "leftSearchRadiusSourcePixels": left[
                        "searchRadiusSourcePixels"
                    ],
                    "rightSearchRadiusSourcePixels": right[
                        "searchRadiusSourcePixels"
                    ],
                    "overlapFrames": overlap,
                    "overlapFractionOfShorterTopSegment": (
                        overlap / shorter if shorter else 0.0
                    ),
                }
            )
    return output


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

    runs = [
        _run_radius(radius, args.cryo_root, priors)
        for radius in SEARCH_RADII
    ]
    reproducibility = _pairwise_reproducibility(runs)

    successful_radii = [
        int(run["searchRadiusSourcePixels"])
        for run in runs
        if int(run["acceptedSegmentCount"]) > 0
    ]
    reproducible_pairs = [
        row
        for row in reproducibility
        if float(row["overlapFractionOfShorterTopSegment"]) >= 0.8
        and int(row["overlapFrames"]) >= strict.MIN_SEGMENT_SPAN
    ]

    report = {
        "schema": "ph-a06-radial-expanded-prior-diagnostic.v1",
        "schemaVersion": "1",
        "task": "TASK-A06",
        "recordedAt": "2026-09-09",
        "status": "diagnostic-only",
        "fixedRegistration": {
            "proximalAtlasZ": proximal_z,
            "distalAtlasZ": distal_z,
            "orientation": orientation,
            "radialAtlasPriorTissueSupport": diagnostics[
                "radial_artery"
            ],
            "atlasGeometryUsedAsSubjectGeometry": False,
        },
        "fixedQualityThresholds": {
            "candidateMinCircularity": strict.QUALITY_MIN_CIRCULARITY,
            "candidateMinContrast": strict.QUALITY_MIN_CONTRAST,
            "candidateMaxPriorDistanceSourcePixels": (
                strict.QUALITY_MAX_PRIOR_DISTANCE
            ),
            "candidateMaxAreaPixels": strict.QUALITY_MAX_AREA,
            "acceptedSegmentMinSpanFrames": strict.MIN_SEGMENT_SPAN,
            "acceptedSegmentMinCoverage": strict.ACCEPT_MIN_COVERAGE,
            "acceptedSegmentMinMedianCircularity": (
                strict.ACCEPT_MIN_MEDIAN_CIRCULARITY
            ),
            "acceptedSegmentMinP25Circularity": (
                strict.ACCEPT_MIN_P25_CIRCULARITY
            ),
            "acceptedSegmentMinMedianContrast": (
                strict.ACCEPT_MIN_MEDIAN_CONTRAST
            ),
            "acceptedSegmentMinP25Contrast": (
                strict.ACCEPT_MIN_P25_CONTRAST
            ),
        },
        "searchRuns": runs,
        "pairwiseTopSegmentReproducibility": reproducibility,
        "decision": {
            "searchRadiiWithAcceptedSegment": successful_radii,
            "reproducibleAcceptedPairCount": len(reproducible_pairs),
            "classification": (
                "reproducible-bounded-segment-signal"
                if reproducible_pairs
                else "not-established"
            ),
            "representationGenerated": False,
            "automaticPromotionAllowed": False,
        },
        "claims": {
            "radialArteryRepresentationGenerated": False,
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
        / "a06-radial-expanded-prior-diagnostic.v0.json"
    ).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "searchRuns": runs,
                "pairwiseTopSegmentReproducibility": reproducibility,
                "decision": report["decision"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
