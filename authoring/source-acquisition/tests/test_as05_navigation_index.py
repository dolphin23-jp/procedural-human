from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "review"))

import as05_build_navigation_index as as05


class AS05NavigationIndexTests(unittest.TestCase):
    def setUp(self):
        self.inventory = ROOT / "source-archives" / "vhf-whole-body-inventory-20260910.json"

    def test_production_inventory_builds_bounded_source_navigation(self):
        result = as05.build_navigation_index(self.inventory)
        self.assertEqual(result["schema"], "ph-as05-source-navigation.v1")
        self.assertEqual(result["task"], "TASK-AS05")
        self.assertEqual(result["coordinateSpace"], "source-image-stack")
        self.assertEqual(result["counts"]["listedSourceCount"], 5186)
        self.assertEqual(result["counts"]["usableImageCount"], 5184)
        self.assertEqual(result["counts"]["unavailableSourceCount"], 2)
        self.assertTrue(all(value is False for value in result["claims"].values()))

        frames = result["frames"]
        self.assertEqual(frames[0]["filename"], "avf1001a.png")
        self.assertEqual(frames[-1]["filename"], "avf2730b.png")
        self.assertEqual(frames[3297]["availability"], "provider-listed-zero-byte")
        self.assertEqual(frames[3298]["availability"], "provider-listed-zero-byte")
        self.assertEqual(result["a05Reference"]["firstIndex"], 1698)
        self.assertEqual(result["a05Reference"]["lastIndex"], 2148)

    def test_navigation_index_is_deterministic_for_same_inventory(self):
        first = as05.build_navigation_index(self.inventory)
        second = as05.build_navigation_index(self.inventory)
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "as05-source-index.json"
            written = as05.write_index(self.inventory, output)
            self.assertEqual(json.loads(output.read_text()), written)

    def test_zero_byte_availability_change_fails_closed(self):
        inventory = json.loads(self.inventory.read_text())
        inventory["frames"][3297]["source"]["listedByteSize"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, "provider availability changed"):
                as05.build_navigation_index(path)


if __name__ == "__main__":
    unittest.main()
