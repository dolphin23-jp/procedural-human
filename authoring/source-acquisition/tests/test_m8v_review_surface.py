from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/review/m8v_build_review_surface.py"
SPEC = importlib.util.spec_from_file_location("m8v_review_surface", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class M8VReviewSurfaceTests(unittest.TestCase):
    def _write(self, root: Path, name: str, value: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        return path

    def _inputs(self, root: Path) -> dict[str, Path]:
        frames = []
        for index in range(420):
            nominal = 1560 + index // 3
            suffix = "abc"[index % 3]
            filename = f"avf{nominal:04d}{suffix}.png"
            frames.append(
                {
                    "index": index,
                    "filename": filename,
                    "source": {
                        "url": f"https://example.test/{filename}",
                        "path": f"PNG_format/thorax/{filename}",
                        "listedByteSize": 100,
                    },
                }
            )
        inventory = {
            "kind": "vhf-whole-body-inventory",
            "coordinateSpace": "source-image-stack",
            "frameCount": len(frames),
            "documentedGeometry": {"widthPixels": 2048, "heightPixels": 1216},
            "terms": {"attribution": "test"},
            "frames": frames,
        }

        tracks = []
        counts = [53] * 16 + [52]
        for ordinal, count in enumerate(counts):
            if ordinal == 0:
                track_class = "ulnar-anchor-linked-continuity"
                vessel_class = "anchor-linked-arterial-candidate"
            elif ordinal <= 8:
                track_class = "anonymous-branch-search"
                vessel_class = "vessel-like-unknown"
            else:
                track_class = "anonymous-superficial-search"
                vessel_class = "superficial-vessel-like-unknown"
            observations = [
                {
                    "wholeBodyFrameIndex": 20 + offset,
                    "xFullImagePixels": 1500.0 + ordinal,
                    "yFullImagePixels": 500.0 + offset,
                    "depthPixels": 8.0 if ordinal > 8 else None,
                }
                for offset in range(count)
            ]
            tracks.append(
                {
                    "id": f"track.{ordinal:02d}",
                    "trackClass": track_class,
                    "sourceClassification": "test-candidate",
                    "identity": {
                        "namedIdentityStatus": "anonymous-unresolved",
                        "vesselClassStatus": vessel_class,
                        "anchorAnatomicalId": None,
                    },
                    "reviewStatus": "unreviewed-as-complete-track",
                    "observationCount": count,
                    "minWholeBodyFrameIndex": 20,
                    "maxWholeBodyFrameIndex": 20 + count - 1,
                    "observations": observations,
                }
            )
        graph = {
            "schema": "ph-m8v-candidate-vessel-track-graph.v1",
            "task": "TASK-V04",
            "status": "complete",
            "tracks": tracks,
            "claims": {
                "sourceIndex3DTrackGraphEstablished": True,
                "patientSpaceGeometry": False,
            },
        }
        registration = {
            "schema": "ph-m8v-ct-cryo-registration-scaffold.v1",
            "task": "TASK-V02",
            "status": "complete",
            "support": {"nominalIndexStart": 1567, "nominalIndexStop": 1685},
            "claims": {"patientSpaceGeometry": False},
        }
        landmarks = {
            "schema": "ph-m8v-upper-extremity-landmark-graph.v1",
            "task": "TASK-V03",
            "status": "complete",
            "nodes": [],
            "relations": [],
            "unresolvedRequiredLandmarks": [],
        }
        radial = {
            "schema": "ph-m8v-radial-artery-identity-evidence.v1",
            "task": "TASK-V05",
            "status": "complete",
            "decision": {"radialArteryPromotionAllowed": False},
            "promotionGateEvaluations": [],
        }
        superficial = {
            "schema": "ph-m8v-superficial-venous-network-evidence.v1",
            "task": "TASK-V06",
            "status": "complete",
            "decision": {"observedSuperficialVeinStructureEstablished": False},
            "promotionGateEvaluations": [],
        }
        return {
            "inventory_path": self._write(root, "inventory.json", inventory),
            "registration_path": self._write(root, "registration.json", registration),
            "landmarks_path": self._write(root, "landmarks.json", landmarks),
            "tracks_path": self._write(root, "tracks.json", graph),
            "radial_path": self._write(root, "radial.json", radial),
            "superficial_path": self._write(root, "superficial.json", superficial),
        }

    def test_review_manifest_preserves_coordinate_space_and_false_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._inputs(Path(directory))
            record, web = MODULE.build(recorded_at="2026-09-11", **paths)
        self.assertEqual(record["trackCoverage"]["totalTrackCount"], 17)
        self.assertEqual(record["trackCoverage"]["directObservationCount"], 900)
        self.assertEqual(record["coordinatePolicy"]["patientSpaceClaim"], False)
        self.assertFalse(record["claims"]["humanAnatomicalReviewCompleted"])
        self.assertFalse(record["claims"]["radialArteryIdentityEstablished"])
        self.assertFalse(record["claims"]["observedSuperficialVeinStructureEstablished"])
        self.assertTrue(any(frame["ct"]["available"] for frame in web["frames"]))
        supported = [
            frame
            for frame in web["frames"]
            if frame["ct"]["registrationStatus"] == "bounded-bone-landmark-scaffold"
        ]
        self.assertTrue(supported)
        self.assertTrue(
            all(
                observation["directSourceObservation"]
                for frame in web["frames"]
                for observation in frame["observations"]
            )
        )

    def test_rejects_pre_promoted_radial_identity_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self._inputs(root)
            radial_path = paths["radial_path"]
            radial = json.loads(radial_path.read_text())
            radial["decision"]["radialArteryPromotionAllowed"] = True
            radial_path.write_text(json.dumps(radial) + "\n")
            with self.assertRaises(MODULE.ReviewSurfaceError):
                MODULE.build(recorded_at="2026-09-11", **paths)


if __name__ == "__main__":
    unittest.main()
