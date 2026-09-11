from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "authoring/source-acquisition/m8v_build_upper_extremity_landmark_graph.py"
SPEC = importlib.util.spec_from_file_location("m8v_landmarks", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LandmarkGraphTests(unittest.TestCase):
    def registration(self) -> dict:
        return json.loads(
            (ROOT / "authoring/outputs/m8v-v02-ct-cryo-registration-scaffold-20260910.json").read_text(
                encoding="utf-8"
            )
        )

    def a05(self) -> dict:
        return json.loads(
            (ROOT / "authoring/outputs/a05-real-v0-output-provenance-20260909.json").read_text(
                encoding="utf-8"
            )
        )

    def build(self, registration: dict | None = None, a05: dict | None = None) -> dict:
        return MODULE.build_landmark_graph(
            registration or self.registration(),
            a05 or self.a05(),
            registration_path="authoring/outputs/m8v-v02-ct-cryo-registration-scaffold-20260910.json",
            a05_path="authoring/outputs/a05-real-v0-output-provenance-20260909.json",
            recorded_at="2026-09-10",
        )

    def test_builds_mixed_evidence_graph_without_promoting_named_landmarks(self) -> None:
        graph = self.build()
        self.assertEqual(len(graph["nodes"]), 10)
        self.assertEqual(len(graph["unresolvedRequiredLandmarks"]), 5)
        self.assertTrue(graph["decision"]["usableForTaskV04"])
        self.assertFalse(graph["decision"]["namedMuscleLandmarksEstablished"])
        self.assertFalse(graph["claims"]["patientSpaceGeometry"])
        self.assertFalse(graph["claims"]["radialArteryIdentityEstablished"])
        self.assertFalse(graph["claims"]["superficialVeinIdentityEstablished"])
        unresolved = {node["id"] for node in graph["nodes"] if node["evidenceStatus"] == "unresolved"}
        self.assertEqual(unresolved, set(MODULE.UNRESOLVED_NAMED_LANDMARKS))

    def test_bone_and_region_evidence_remain_distinct(self) -> None:
        graph = self.build()
        by_id = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(by_id["structure.radius.left"]["sourceClass"], "same-subject-cadaver-plus-radiological")
        self.assertEqual(by_id["structure.radius.left"]["support"]["frameCount"], 357)
        self.assertEqual(by_id["vhf.left.forearm.region.subcutaneous-soft-tissue.v0"]["sourceClass"], "same-subject-algorithm-derived")
        self.assertEqual(by_id["vhf.left.forearm.region.subcutaneous-soft-tissue.v0"]["support"]["frameCount"], 451)

    def test_rejects_patient_space_or_medical_registration_promotion(self) -> None:
        registration = copy.deepcopy(self.registration())
        registration["claims"]["patientSpaceGeometry"] = True
        with self.assertRaises(MODULE.LandmarkGraphError):
            self.build(registration=registration)

        registration = copy.deepcopy(self.registration())
        registration["claims"]["ctCryosectionMedicalRegistrationEstablished"] = True
        with self.assertRaises(MODULE.LandmarkGraphError):
            self.build(registration=registration)

    def test_rejects_named_structure_smuggled_in_as_generic_a05_region(self) -> None:
        a05 = copy.deepcopy(self.a05())
        a05["nonvascular"]["generated"][2]["draftLabel"] = "brachioradialis"
        with self.assertRaises(MODULE.LandmarkGraphError):
            self.build(a05=a05)

    def test_rejects_unverified_persistent_a05_output(self) -> None:
        a05 = copy.deepcopy(self.a05())
        a05["persistentOutput"]["postUploadVerification"]["sha256Matches"] = False
        with self.assertRaises(MODULE.LandmarkGraphError):
            self.build(a05=a05)

    def test_committed_v03_record_validates(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/assets/m8v-upper-extremity-landmark-graph.v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        record = json.loads(
            (ROOT / "authoring/outputs/m8v-v03-upper-extremity-landmark-graph-20260910.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(record)
        self.assertFalse(record["claims"]["namedMuscleIdentityEstablished"])
        self.assertEqual(record["decision"]["nextTask"], "TASK-V04")


if __name__ == "__main__":
    unittest.main()
