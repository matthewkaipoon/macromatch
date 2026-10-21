"""Offline self-checks. No internet and no API key required."""
import unittest
from audits.usda.audit_usda import extract_food, nutrient_record, choose_samples


class AuditTests(unittest.TestCase):
    def test_detail_nested_nutrients(self):
        food = {"fdcId": 123, "dataType": "SR Legacy", "description": "Test chickpeas", "foodNutrients": [
            {"nutrient": {"id": 1003, "unitName": "g"}, "amount": 9},
            {"nutrient": {"id": 1004, "unitName": "g"}, "amount": 3},
            {"nutrient": {"id": 1005, "unitName": "g"}, "amount": 24},
            {"nutrient": {"id": 1079, "unitName": "g"}, "amount": 8},
            {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 164},
        ]}
        result = extract_food(food)
        self.assertTrue(result["usable_all"])
        self.assertEqual(result["energy_nutrient_id"], 1008)
        self.assertEqual(result["protein_g"], 9)
        self.assertEqual(result["fiber_g"], 8)
        self.assertEqual(result["schema_nested_count"], 5)

    def test_flat_schema_and_zero_is_present(self):
        food = {"fdcId": 2, "dataType": "Foundation", "description": "Zero-test", "foodNutrients": [
            {"nutrientId": 1003, "unitName": "G", "value": 0},
            {"nutrientId": 1004, "unitName": "G", "value": 0},
            {"nutrientId": 1005, "unitName": "G", "value": 0},
            {"nutrientId": 1079, "unitName": "G", "value": 0},
            {"nutrientId": 2048, "unitName": "KCAL", "value": 0},
        ]}
        result = extract_food(food)
        self.assertTrue(result["complete_all"])
        self.assertEqual(result["schema_flat_count"], 5)

    def test_energy_preference_and_unit_conversion(self):
        food = {"fdcId": 3, "foodNutrients": [
            {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 200},
            {"nutrient": {"id": 2048, "unitName": "kJ"}, "amount": 418.4},
            {"nutrient": {"id": 1003, "unitName": "mg"}, "amount": 1100},
        ]}
        result = extract_food(food)
        self.assertAlmostEqual(result["energy_kcal"], 100)
        self.assertAlmostEqual(result["protein_g"], 1.1)
        self.assertEqual(result["energy_nutrient_id"], 2048)
        self.assertIn("multiple_energy_definitions", result["flags"])

    def test_missing_fibre_not_turned_into_zero(self):
        food = {"fdcId": 4, "foodNutrients": [
            {"nutrient": {"id": 1003, "unitName": "g"}, "amount": 10},
            {"nutrient": {"id": 1004, "unitName": "g"}, "amount": 0},
            {"nutrient": {"id": 1005, "unitName": "g"}, "amount": 40},
            {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 200},
        ]}
        result = extract_food(food)
        self.assertTrue(result["complete_core"])
        self.assertFalse(result["complete_all"])
        self.assertIsNone(result["fiber_g"])

    def test_round_robin_sample(self):
        buckets = {
            ("rice", "Foundation"): [{"fdcId": 1}, {"fdcId": 2}],
            ("rice", "SR Legacy"): [{"fdcId": 1}, {"fdcId": 3}],
        }
        selected, provenance = choose_samples(buckets, 3, 2)
        self.assertEqual(selected, [1, 2, 3])
        self.assertEqual(len(provenance[1]), 2)


    def test_offline_integration_outputs(self):
        import io
        import json
        import os
        import tempfile
        from pathlib import Path
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from audits.usda import audit_usda

        def fake_post(client, path, payload, label):
            client.count += 1
            if path == "/foods/search":
                base = abs(hash((payload["query"], payload["dataType"][0]))) % 1_000_000
                return {"totalHits": 10, "foods": [
                    {"fdcId": base + j, "description": payload["query"] + " test"}
                    for j in range(3)
                ]}
            if path == "/foods":
                return [{"fdcId": i, "description": "Test food " + str(i), "dataType": "SR Legacy",
                    "foodNutrients": [
                        {"nutrient": {"id": nid, "unitName": "kcal" if nid == 1008 else "g"}, "amount": amount}
                        for nid, amount in [(1003, 10), (1004, 4), (1005, 30), (1079, 3), (1008, 200)]
                    ]} for i in payload["fdcIds"]]
            raise AssertionError("Unexpected endpoint")

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"USDA_API_KEY": "NOT_A_REAL_KEY"}):
                with patch.object(audit_usda.FDCClient, "post", fake_post):
                    with redirect_stdout(io.StringIO()):
                        code = audit_usda.main(["--out", tmp, "--max-foods", "16", "--per-bucket", "1"])
            self.assertEqual(code, 0)
            summary = json.loads((Path(tmp) / "audit_summary.json").read_text())
            self.assertEqual(summary["completion"], "complete")
            self.assertEqual(summary["sampled_detail_records"], 16)
            self.assertTrue((Path(tmp) / "foods_audit.csv").is_file())
            self.assertTrue((Path(tmp) / "request_manifest.json").is_file())
            self.assertNotIn("NOT_A_REAL_KEY", (Path(tmp) / "request_manifest.json").read_text())


if __name__ == "__main__":
    unittest.main()
