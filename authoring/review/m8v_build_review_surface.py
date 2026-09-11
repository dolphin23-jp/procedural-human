"""Build TASK-V07 authoring provenance and transient web-review manifest.

The browser surface is intentionally a review aid. Cryosection x/y overlays remain
in provider source-image pixels; CT is shown in its own source-pixel space. A
shared nominal source index synchronizes the two panels for inspection but is not
Patient Space and does not confer medical registration or vessel identity.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


CT_IMAGE_BASE = (
    "https://data.lhncbc.nlm.nih.gov/public/Visible-Human/Female-Images/"
    "PNG_format/radiological/normalCT"
)
CT_PROBE_START = 1567
CT_PROBE_STOP = 1717


class ReviewSurfaceError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReviewSurfaceError(f"{path} must contain a JSON object")
    return value


def _sha256_path(path: Path) -> str:
    h = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewSurfaceError(message)


def _source_ref(path: Path, data: dict[str, Any]) -> dict[str, str]:
    schema = data.get("schema") or data.get("kind")
    _require(isinstance(schema, str) and schema, f"{path} must declare schema/kind")
    return {
        "path": path.as_posix(),
        "sha256": _sha256_path(path),
        "schema": schema,
    }


def _parse_source_filename(filename: str) -> tuple[int, str]:
    match = re.fullmatch(r"avf(\d{4})([abc])\.png", filename)
    if match is None:
        raise ReviewSurfaceError(f"unexpected VHF cryosection filename: {filename}")
    return int(match.group(1)), match.group(2)


def _validate_inputs(
    inventory: dict[str, Any],
    registration: dict[str, Any],
    landmarks: dict[str, Any],
    tracks: dict[str, Any],
    radial: dict[str, Any],
    superficial: dict[str, Any],
) -> None:
    _require(inventory.get("kind") == "vhf-whole-body-inventory", "unexpected whole-body inventory")
    _require(inventory.get("coordinateSpace") == "source-image-stack", "inventory must remain source-image-stack")
    geometry = inventory.get("documentedGeometry", {})
    _require(geometry.get("widthPixels") == 2048 and geometry.get("heightPixels") == 1216, "unexpected cryosection geometry")
    _require(registration.get("task") == "TASK-V02" and registration.get("status") == "complete", "TASK-V02 must be complete")
    support = registration.get("support", {})
    _require(support.get("nominalIndexStart") == 1567 and support.get("nominalIndexStop") == 1685, "TASK-V02 bounded CT support changed")
    _require(registration.get("claims", {}).get("patientSpaceGeometry") is False, "TASK-V02 cannot claim Patient Space")
    _require(landmarks.get("task") == "TASK-V03" and landmarks.get("status") == "complete", "TASK-V03 must be complete")
    _require(tracks.get("task") == "TASK-V04" and tracks.get("status") == "complete", "TASK-V04 must be complete")
    track_claims = tracks.get("claims", {})
    _require(track_claims.get("sourceIndex3DTrackGraphEstablished") is True, "TASK-V04 source-index graph is required")
    _require(track_claims.get("patientSpaceGeometry") is False, "TASK-V04 cannot claim Patient Space")
    _require(radial.get("task") == "TASK-V05" and radial.get("status") == "complete", "TASK-V05 must be complete")
    _require(radial.get("decision", {}).get("radialArteryPromotionAllowed") is False, "V07 must not start from pre-promoted radial identity")
    _require(superficial.get("task") == "TASK-V06" and superficial.get("status") == "complete", "TASK-V06 must be complete")
    _require(superficial.get("decision", {}).get("observedSuperficialVeinStructureEstablished") is False, "V07 must not start from pre-promoted superficial vein structure")


def _frame_observations(tracks: dict[str, Any]) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    track_rows: list[dict[str, Any]] = []
    for track in tracks.get("tracks", []):
        track_id = str(track["id"])
        track_class = str(track["trackClass"])
        identity = track.get("identity", {})
        observations = track.get("observations", [])
        for observation in observations:
            frame_index = int(observation["wholeBodyFrameIndex"])
            row = {
                "trackId": track_id,
                "trackClass": track_class,
                "sourceClassification": str(track["sourceClassification"]),
                "xFullImagePixels": float(observation["xFullImagePixels"]),
                "yFullImagePixels": float(observation["yFullImagePixels"]),
                "depthPixels": observation.get("depthPixels"),
                "directSourceObservation": True,
            }
            by_frame[frame_index].append(row)
        track_rows.append(
            {
                "id": track_id,
                "trackClass": track_class,
                "sourceClassification": str(track["sourceClassification"]),
                "namedIdentityStatus": str(identity.get("namedIdentityStatus", "unknown")),
                "vesselClassStatus": str(identity.get("vesselClassStatus", "unknown")),
                "anchorAnatomicalId": identity.get("anchorAnatomicalId"),
                "observationCount": int(track["observationCount"]),
                "minWholeBodyFrameIndex": int(track["minWholeBodyFrameIndex"]),
                "maxWholeBodyFrameIndex": int(track["maxWholeBodyFrameIndex"]),
                "reviewStatus": str(track["reviewStatus"]),
            }
        )
    _require(by_frame, "TASK-V04 contains no observations")
    return by_frame, track_rows


def build(
    *,
    inventory_path: Path,
    registration_path: Path,
    landmarks_path: Path,
    tracks_path: Path,
    radial_path: Path,
    superficial_path: Path,
    recorded_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    inventory = _read_json(inventory_path)
    registration = _read_json(registration_path)
    landmarks = _read_json(landmarks_path)
    tracks = _read_json(tracks_path)
    radial = _read_json(radial_path)
    superficial = _read_json(superficial_path)
    _validate_inputs(inventory, registration, landmarks, tracks, radial, superficial)

    by_frame, track_rows = _frame_observations(tracks)
    first_index = min(by_frame)
    last_index = max(by_frame)
    inventory_frames = inventory.get("frames", [])
    _require(len(inventory_frames) == inventory.get("frameCount"), "inventory frame count mismatch")
    _require([row.get("index") for row in inventory_frames] == list(range(len(inventory_frames))), "inventory indices must be contiguous")
    selected_inventory = inventory_frames[first_index : last_index + 1]
    _require(selected_inventory and selected_inventory[0]["index"] == first_index and selected_inventory[-1]["index"] == last_index, "review frame range is outside inventory")

    web_frames: list[dict[str, Any]] = []
    ct_probe_linked = 0
    ct_scaffold = 0
    for row in selected_inventory:
        frame_index = int(row["index"])
        filename = str(row["filename"])
        nominal_index, suffix = _parse_source_filename(filename)
        ct: dict[str, Any]
        if CT_PROBE_START <= nominal_index <= CT_PROBE_STOP:
            ct_probe_linked += 1
            registration_status = (
                "bounded-bone-landmark-scaffold"
                if 1567 <= nominal_index <= 1685
                else "probe-available-registration-unsupported"
            )
            if registration_status == "bounded-bone-landmark-scaffold":
                ct_scaffold += 1
            ct = {
                "available": True,
                "sourceUrl": f"{CT_IMAGE_BASE}/cvf{nominal_index:04d}f.png",
                "filename": f"cvf{nominal_index:04d}f.png",
                "synchronization": "shared-nominal-source-index-for-review-only",
                "registrationStatus": registration_status,
            }
        else:
            ct = {
                "available": False,
                "sourceUrl": None,
                "filename": None,
                "synchronization": "no-bounded-probe-image-linked",
                "registrationStatus": "unknown-not-registered-by-this-scaffold",
            }
        web_frames.append(
            {
                "wholeBodyFrameIndex": frame_index,
                "sourceFilename": filename,
                "nominalIndex": nominal_index,
                "cryosectionSuffix": suffix,
                "cryosection": {
                    "sourceUrl": str(row["source"]["url"]),
                    "sourcePath": str(row["source"]["path"]),
                    "listedByteSize": int(row["source"]["listedByteSize"]),
                    "widthPixels": 2048,
                    "heightPixels": 1216,
                },
                "ct": ct,
                "observations": sorted(
                    by_frame.get(frame_index, []), key=lambda item: item["trackId"]
                ),
            }
        )

    counts = defaultdict(int)
    for row in track_rows:
        counts[row["trackClass"]] += 1
    direct_observations = sum(row["observationCount"] for row in track_rows)
    _require(len(track_rows) == 17 and direct_observations == 900, "TASK-V04 expected graph invariants changed")
    _require(counts["ulnar-anchor-linked-continuity"] == 1, "expected one ulnar anchor-linked track")
    _require(counts["anonymous-branch-search"] == 8, "expected eight anonymous arterial tracks")
    _require(counts["anonymous-superficial-search"] == 8, "expected eight anonymous superficial tracks")

    evidence_paths = (
        inventory_path,
        registration_path,
        landmarks_path,
        tracks_path,
        radial_path,
        superficial_path,
    )
    evidence_data = (
        inventory,
        registration,
        landmarks,
        tracks,
        radial,
        superficial,
    )
    input_evidence = [
        _source_ref(path, data) for path, data in zip(evidence_paths, evidence_data)
    ]
    record = {
        "schema": "ph-m8v-multimodal-review-surface.v1",
        "schemaVersion": "1",
        "task": "TASK-V07",
        "recordedAt": recorded_at,
        "status": "complete",
        "route": "?m8v-review=1",
        "inputEvidence": input_evidence,
        "coordinatePolicy": {
            "cryosectionSpace": "source-image-pixels-plus-frame-index",
            "ctSpace": "ct-source-pixels",
            "synchronization": "shared-nominal-source-index-for-review-only",
            "boundedCtRegistrationStart": 1567,
            "boundedCtRegistrationStop": 1685,
            "patientSpaceClaim": False,
        },
        "frameCoverage": {
            "firstWholeBodyFrameIndex": first_index,
            "lastWholeBodyFrameIndex": last_index,
            "frameCount": len(web_frames),
            "ctProbeLinkedFrameCount": ct_probe_linked,
            "boundedCtScaffoldFrameCount": ct_scaffold,
        },
        "trackCoverage": {
            "totalTrackCount": len(track_rows),
            "ulnarAnchorLinkedTrackCount": counts["ulnar-anchor-linked-continuity"],
            "anonymousArterialTrackCount": counts["anonymous-branch-search"],
            "anonymousSuperficialTrackCount": counts["anonymous-superficial-search"],
            "directObservationCount": direct_observations,
        },
        "capabilities": {
            "cryosectionDisplay": True,
            "ctSideBySideDisplay": True,
            "frameSynchronization": True,
            "candidateTrackOverlay": True,
            "landmarkEvidencePanel": True,
            "promotionGatePanel": True,
            "provenancePanel": True,
            "identityPromotionByUi": False,
        },
        "claims": {
            "multimodalReviewSurfaceEstablished": True,
            "humanAnatomicalReviewCompleted": False,
            "ctCryosectionMedicalRegistrationEstablished": False,
            "patientSpaceGeometry": False,
            "radialArteryIdentityEstablished": False,
            "observedSuperficialVeinStructureEstablished": False,
            "namedSuperficialVeinIdentityEstablished": False,
            "medicalValidation": False,
            "automaticPromotionAllowed": False,
        },
    }

    web_manifest = {
        "schema": "ph-m8v-web-review-manifest.v1",
        "schemaVersion": "1",
        "task": "TASK-V07",
        "surfaceRecord": record,
        "imageDelivery": {
            "cryosection": "live-authoritative-provider-url-from-committed-inventory",
            "ct": "live-authoritative-provider-url-within-existing-bounded-probe-range",
            "contentAddressedAtBrowserRender": False,
            "snapshotNotice": "Live provider images are used for review convenience; the committed evidence records remain authoritative for claims and lineage.",
        },
        "sourceTerms": inventory.get("terms", {}),
        "tracks": track_rows,
        "landmarks": landmarks.get("nodes", []),
        "landmarkRelations": landmarks.get("relations", []),
        "unresolvedRequiredLandmarks": landmarks.get("unresolvedRequiredLandmarks", []),
        "radialPromotionGates": radial.get("promotionGateEvaluations", []),
        "superficialPromotionGates": superficial.get("promotionGateEvaluations", []),
        "frames": web_frames,
        "claims": record["claims"],
    }
    return record, web_manifest


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--tracks", type=Path, required=True)
    parser.add_argument("--radial", type=Path, required=True)
    parser.add_argument("--superficial", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--record-output", type=Path)
    parser.add_argument("--web-output", type=Path)
    args = parser.parse_args()

    record, web_manifest = build(
        inventory_path=args.inventory,
        registration_path=args.registration,
        landmarks_path=args.landmarks,
        tracks_path=args.tracks,
        radial_path=args.radial,
        superficial_path=args.superficial,
        recorded_at=args.recorded_at,
    )
    if args.record_output is not None:
        _write_json(args.record_output, record)
    if args.web_output is not None:
        _write_json(args.web_output, web_manifest)
    if args.record_output is None and args.web_output is None:
        raise ReviewSurfaceError("at least one output path is required")
    print(
        json.dumps(
            {
                "frameCoverage": record["frameCoverage"],
                "trackCoverage": record["trackCoverage"],
                "route": record["route"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
