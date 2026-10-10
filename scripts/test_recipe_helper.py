import json
import subprocess
import unittest
from unittest.mock import patch

try:
    from scripts import recipe_helper
except ModuleNotFoundError:
    import recipe_helper

PAGE = """<html><head><title>Kurczak</title>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage","name":"x"},
{"@type":["Recipe"],"name":"Kurczak curry","recipeYield":"4","recipeIngredient":["500 g kurczaka","1 puszka mleka kokosowego"],
"recipeInstructions":[{"@type":"HowToStep","text":"Pokrój kurczaka."}],"author":"someone"}]}</script>
<style>.a{}</style></head><body><nav>Menu</nav><p>Najlepsze &amp; szybkie curry</p></body></html>"""

ANSWER = {
    "title": "Kurczak curry", "servings": "4", "minutes": 35, "tags": ["szybkie", "", "curry", "a", "b"],
    "ingredients": [
        {"name": "kurczak", "amount": "500 g", "grams": 500, "kcal": 600, "protein_g": 115, "carbs_g": 0, "fat_g": 12},
        {"name": "", "kcal": 5},
        {"name": "sól", "amount": "szczypta", "grams": None, "kcal": -3},
    ],
    "steps": ["Pokrój kurczaka.", " "],
    "note": "",
}


class RecipeHelperTests(unittest.TestCase):
    def test_validate_request(self):
        with self.assertRaises(ValueError):
            recipe_helper.validate_request({"text": " "})
        with self.assertRaises(ValueError):
            recipe_helper.validate_request({"url": "file:///etc/passwd"})
        self.assertEqual(recipe_helper.validate_request({"text": " curry "})["text"], "curry")
        self.assertEqual(recipe_helper.validate_request({"url": "https://example.com/r"})["url"], "https://example.com/r")

    def test_adjust_request_needs_changes_and_keeps_source(self):
        recipe = {"title": "Curry", "ingredients": [{"name": "śmietana"}], "source": "url", "source_url": "https://x.pl/c", "id": 4}
        with self.assertRaises(ValueError):
            recipe_helper.validate_request({"recipe": recipe, "text": " "})
        with self.assertRaises(ValueError):
            recipe_helper.validate_request({"recipe": {"title": "x"}, "text": "bez cebuli"})
        request = recipe_helper.validate_request({"recipe": recipe, "text": "jogurt zamiast śmietany"})
        self.assertNotIn("id", request["recipe"])
        prompt = recipe_helper.build_prompt(request)
        self.assertIn("jogurt zamiast śmietany", prompt)
        self.assertIn("śmietana", prompt)
        self.assertNotIn("https://x.pl/c", prompt)

    @patch.object(recipe_helper.subprocess, "run")
    def test_adjusted_recipe_keeps_its_source(self, run):
        result = {"type": "result", "subtype": "success", "result": json.dumps(ANSWER)}
        run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(result) + "\n", stderr="")
        request = recipe_helper.validate_request({
            "recipe": {"title": "Curry", "ingredients": [], "source": "url", "source_url": "https://x.pl/c"}, "text": "bez cebuli",
        })
        recipe = recipe_helper.run_draft(request, cli_path="claude", model="sonnet", record_usage=lambda *args: None)
        self.assertEqual((recipe["source"], recipe["source_url"]), ("url", "https://x.pl/c"))

    def test_structured_recipe_found_in_graph(self):
        recipe = recipe_helper.structured_recipe(PAGE)
        self.assertEqual(recipe["name"], "Kurczak curry")
        self.assertEqual(recipe["recipeIngredient"][1], "1 puszka mleka kokosowego")
        self.assertNotIn("author", recipe)

    def test_visible_text_drops_scripts_and_nav(self):
        text = recipe_helper.visible_text(PAGE)
        self.assertIn("Najlepsze & szybkie curry", text)
        self.assertNotIn("Menu", text)
        self.assertNotIn("@graph", text)

    def test_prompt_uses_structured_data_for_urls_and_context_for_generation(self):
        prompt = recipe_helper.build_prompt({"url": "https://x.pl/curry", "text": "", "context": ""}, PAGE)
        self.assertIn("1 puszka mleka kokosowego", prompt)
        self.assertNotIn("Najlepsze", prompt)
        prompt = recipe_helper.build_prompt({"url": None, "text": "coś z {kurczakiem}", "context": "Carb up: long ride tomorrow"})
        self.assertIn("coś z {kurczakiem}", prompt)
        self.assertIn("Carb up", prompt)

    def test_parse_recipe_cleans_values(self):
        recipe = recipe_helper.parse_recipe("```json\n" + json.dumps(ANSWER) + "\n```")
        self.assertEqual(recipe["servings"], 4.0)
        self.assertEqual([item["name"] for item in recipe["ingredients"]], ["kurczak", "sól"])
        self.assertEqual(recipe["ingredients"][1]["kcal"], 0.0)
        self.assertEqual(recipe["steps"], ["Pokrój kurczaka."])
        self.assertEqual(recipe["tags"], ["szybkie", "curry", "a", "b"])

    def test_parse_recipe_reports_model_error(self):
        with self.assertRaisesRegex(ValueError, "not a recipe"):
            recipe_helper.parse_recipe('{"error": "The page is not a recipe"}')

    def test_private_hosts_are_refused(self):
        with self.assertRaises(ValueError):
            recipe_helper.fetch_page("http://127.0.0.1:8000/nutrition/recipes")

    @patch.object(recipe_helper.subprocess, "run")
    def test_run_draft_generates_without_fetching(self, run):
        result = {"type": "result", "subtype": "success", "result": json.dumps(ANSWER)}
        run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(result) + "\n", stderr="")
        usage = []
        with patch.object(recipe_helper, "fetch_page") as fetch:
            recipe = recipe_helper.run_draft({"url": None, "text": "curry", "context": ""}, cli_path="claude", model="sonnet",
                                             record_usage=lambda *args: usage.append(args))
        fetch.assert_not_called()
        self.assertEqual((recipe["source"], recipe["source_url"]), ("generated", None))
        self.assertTrue(usage[0][1])
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--tools") + 1], "")


if __name__ == "__main__":
    unittest.main()
