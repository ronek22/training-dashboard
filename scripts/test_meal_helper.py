import base64
import json
import subprocess
import unittest
from unittest.mock import patch

try:
    from scripts import meal_helper
except ModuleNotFoundError:
    import meal_helper

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()


class MealHelperTests(unittest.TestCase):
    def test_needs_text_or_photo(self):
        with self.assertRaises(ValueError):
            meal_helper.validate_request({"text": "  "})
        self.assertEqual(meal_helper.validate_request({"text": " 2 jajka "}), ("2 jajka", None))

    def test_rejects_unknown_image_type_and_bad_base64(self):
        with self.assertRaises(ValueError):
            meal_helper.validate_request({"image": {"media_type": "image/heic", "data": PNG}})
        with self.assertRaises(ValueError):
            meal_helper.validate_request({"image": {"media_type": "image/png", "data": "not base64!"}})

    def test_message_puts_image_before_text(self):
        message = json.loads(meal_helper.build_message("kebab", {"media_type": "image/png", "data": PNG}))
        content = message["message"]["content"]
        self.assertEqual([block["type"] for block in content], ["image", "text"])
        self.assertIn("kebab", content[1]["text"])

    def test_parse_items_cleans_values(self):
        answer = '```json\n{"items":[{"name":"ryż","grams":"200","kcal":260,"protein_g":5,"carbs_g":56,"fat_g":0.6,"confidence":"sure"},' \
                 '{"name":"","kcal":10},{"name":"sos","kcal":-5}],"note":"porcja sosu niepewna"}\n```'
        parsed = meal_helper.parse_items(answer)
        self.assertEqual([item["name"] for item in parsed["items"]], ["ryż", "sos"])
        self.assertEqual(parsed["items"][0]["grams"], 200.0)
        self.assertEqual(parsed["items"][0]["confidence"], "medium")
        self.assertEqual(parsed["items"][1]["kcal"], 0.0)
        self.assertEqual(parsed["note"], "porcja sosu niepewna")

    def test_parse_label_copies_values_and_checks_barcode(self):
        label = meal_helper.parse_label('{"name":"Frankfurterki z jagnięciną","brand":"Pikok","barcode":"2012 3456",'
                                        '"per_100g":{"kcal":"251","protein_g":14.2,"carbs_g":null,"fat_g":21},"serving_g":50,"package_g":"400"}')
        self.assertEqual(label["per_100g"], {"kcal": 251.0, "protein_g": 14.2, "carbs_g": 0.0, "fat_g": 21.0})
        self.assertEqual((label["barcode"], label["package_g"], label["source"]), ("20123456", 400.0, "label"))
        self.assertIsNone(meal_helper.parse_label('{"name":"x","barcode":"123","per_100g":{"kcal":1}}')["barcode"])
        with self.assertRaises(ValueError):
            meal_helper.parse_label('{"name":"x","per_100g":{}}')
        with self.assertRaisesRegex(ValueError, "blurry"):
            meal_helper.parse_label('{"error":"The label is blurry"}')

    def test_label_message_sends_image_first(self):
        message = json.loads(meal_helper.build_label_message({"media_type": "image/png", "data": PNG}, "parówki"))
        content = message["message"]["content"]
        self.assertEqual([block["type"] for block in content], ["image", "text"])
        self.assertIn("w 100 g", content[1]["text"])

    def test_ideas_request_is_bounded(self):
        request = meal_helper.validate_ideas_request({"meal": "dinner", "kcal": 1172.4, "protein_g": 66, "hour": 18,
                                                      "eaten": [" rosół ", ""], "note": " mam jajka "})
        self.assertEqual((request["kcal"], request["eaten"], request["note"]), (1172, ["rosół"], "mam jajka"))
        for bad in ({"meal": "brunch", "kcal": 500}, {"meal": "snack", "kcal": 10}, {"meal": "snack", "kcal": 300, "hour": 25}):
            with self.assertRaises(ValueError):
                meal_helper.validate_ideas_request(bad)

    def test_ideas_message_carries_budget_and_note(self):
        request = meal_helper.validate_ideas_request({"meal": "snack", "kcal": 400, "protein_g": 20, "note": "tylko lodówka"})
        text = json.loads(meal_helper.build_ideas_message(request))["message"]["content"][0]["text"]
        self.assertIn("400 kcal, 20 g protein", text)
        self.assertIn("tylko lodówka", text)

    def test_parse_ideas_keeps_ideas_with_items(self):
        parsed = meal_helper.parse_ideas('{"ideas":[{"title":"Skyr z owocami","why":"szybko","items":[{"name":"skyr","grams":300,'
                                         '"kcal":190,"protein_g":33,"carbs_g":12,"fat_g":0.6}]},{"title":"pusty","items":[]}]}')
        self.assertEqual([idea["title"] for idea in parsed["ideas"]], ["Skyr z owocami"])
        self.assertEqual(parsed["ideas"][0]["totals"]["protein_g"], 33.0)
        with self.assertRaises(ValueError):
            meal_helper.parse_ideas('{"ideas":[]}')

    def test_parse_items_rejects_prose(self):
        with self.assertRaises(ValueError):
            meal_helper.parse_items("I cannot see any food.")

    @patch.object(meal_helper, "saved_foods_hint", return_value="")
    @patch.object(meal_helper.subprocess, "run")
    def test_run_estimate_reads_result_event_and_records_usage(self, run, _hint):
        result = {"type": "result", "subtype": "success", "result": '{"items":[{"name":"jajko","grams":50,"kcal":72}],"note":""}'}
        run.return_value = subprocess.CompletedProcess([], 0, stdout='{"type":"system"}\n' + json.dumps(result) + "\n", stderr="")
        usage = []
        estimate = meal_helper.run_estimate("jajko", None, cli_path="claude", model="sonnet",
                                            record_usage=lambda *args: usage.append(args))
        self.assertEqual(estimate["items"][0]["kcal"], 72.0)
        self.assertTrue(usage[0][1])
        command = run.call_args.args[0]
        self.assertIn("stream-json", command)
        self.assertEqual(command[command.index("--tools") + 1], "")

    @patch.object(meal_helper, "saved_foods_hint", return_value="")
    @patch.object(meal_helper.subprocess, "run")
    def test_run_estimate_surfaces_claude_errors(self, run, _hint):
        result = {"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "overloaded"}
        run.return_value = subprocess.CompletedProcess([], 1, stdout=json.dumps(result), stderr="")
        with self.assertRaisesRegex(RuntimeError, "overloaded"):
            meal_helper.run_estimate("jajko", None, cli_path="claude", model="sonnet", record_usage=lambda *args: None)


if __name__ == "__main__":
    unittest.main()
