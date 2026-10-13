import json
import sqlite3
import unittest

from fastapi import HTTPException

from backend.app.services import dinner_plan, recipes

MONDAY = "2026-10-05"


class DinnerPlanTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, days_json TEXT);
            CREATE TABLE food_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, meal TEXT NOT NULL,
                source TEXT NOT NULL, raw_text TEXT, created_at TEXT);
            CREATE TABLE dinner_plans (date TEXT PRIMARY KEY, dish TEXT NOT NULL, notes TEXT, kcal REAL, protein_g REAL,
                recipe_id INTEGER, servings REAL NOT NULL DEFAULT 1, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, servings REAL NOT NULL DEFAULT 2,
                minutes INTEGER, source TEXT NOT NULL DEFAULT 'manual', source_url TEXT, ingredients_json TEXT NOT NULL DEFAULT '[]',
                steps_json TEXT NOT NULL DEFAULT '[]', tags_json TEXT NOT NULL DEFAULT '[]', notes TEXT,
                kcal REAL NOT NULL DEFAULT 0, protein_g REAL NOT NULL DEFAULT 0, carbs_g REAL NOT NULL DEFAULT 0,
                fat_g REAL NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            """
        )

    def _plan(self, week_start, days):
        self.conn.execute("INSERT INTO weekly_plans VALUES (?, ?)", (week_start, json.dumps(days)))

    def test_week_is_monday_to_sunday_from_any_day(self):
        week = dinner_plan.build_dinner_week(self.conn, "2026-10-08")
        self.assertEqual(week["week_start"], MONDAY)
        self.assertEqual([day["date"] for day in week["days"]][-1], "2026-10-11")
        self.assertEqual(week["planned"], 0)

    def test_set_update_and_clear(self):
        week = dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": "  Makaron z kurczakiem ", "kcal": 750, "protein_g": 45})
        tuesday = week["days"][1]
        self.assertEqual((tuesday["dish"], tuesday["kcal"], tuesday["protein_g"]), ("Makaron z kurczakiem", 750, 45))
        week = dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": "Ryż z łososiem", "kcal": None})
        self.assertEqual((week["days"][1]["dish"], week["days"][1]["kcal"]), ("Ryż z łososiem", None))
        week = dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": ""})
        self.assertIsNone(week["days"][1]["dish"])
        self.assertEqual(week["planned"], 0)

    def test_rejects_negative_amounts_and_bad_dates(self):
        with self.assertRaises(HTTPException):
            dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": "Pizza", "kcal": -5})
        with self.assertRaises(HTTPException):
            dinner_plan.set_dinner(self.conn, "06-10-2026", {"dish": "Pizza"})

    def test_logged_dinner_and_training_context(self):
        self.conn.execute("INSERT INTO food_entries (date, meal, source) VALUES ('2026-10-05', 'lunch', 'text')")
        self.conn.execute("INSERT INTO food_entries (date, meal, source) VALUES ('2026-10-06', 'dinner', 'text')")
        self._plan(MONDAY, [
            {"date": "2026-10-07", "session_type": "ride", "workout_intent": "easy", "title": "Easy spin", "target_duration_min": 45},
            {"date": "2026-10-08", "session_type": "ride", "workout_intent": "tempo", "title": "Tempo ride", "target_duration_min": 60},
            {"date": "2026-10-09", "session_type": "rest", "title": "Rest"},
        ])
        self._plan("2026-10-12", [{"date": "2026-10-12", "session_type": "ride", "workout_intent": "long", "title": "Long ride", "target_duration_min": 180}])
        days = dinner_plan.build_dinner_week(self.conn, MONDAY)["days"]
        self.assertEqual([day["logged"] for day in days[:2]], [True, False])
        self.assertEqual(days[2]["training"][0]["title"], "Easy spin")
        self.assertIn("Tempo ride tomorrow", days[2]["fuel_hint"])
        self.assertTrue(days[3]["fuel_hint"].startswith("Refuel"))
        self.assertEqual(days[4]["training"], [])
        self.assertIn("Long ride tomorrow", days[6]["fuel_hint"])

    def test_copy_previous_week_fills_only_empty_days(self):
        dinner_plan.set_dinner(self.conn, "2026-09-28", {"dish": "Gulasz", "kcal": 800})
        dinner_plan.set_dinner(self.conn, "2026-09-29", {"dish": "Pierogi"})
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": "Curry"})
        week = dinner_plan.copy_previous_week(self.conn, MONDAY)
        self.assertEqual([day["dish"] for day in week["days"][:3]], ["Gulasz", "Curry", None])
        self.assertEqual(week["days"][0]["kcal"], 800)

    def test_suggestions_rank_by_use(self):
        for day, dish in [("2026-09-01", "Pizza"), ("2026-09-02", "Curry"), ("2026-09-08", "Curry")]:
            dinner_plan.set_dinner(self.conn, day, {"dish": dish})
        self.assertEqual(dinner_plan.build_dinner_week(self.conn, MONDAY)["suggestions"], ["Curry", "Pizza"])


    def _recipe(self, **extra):
        return recipes.create_recipe(self.conn, {
            "title": "Kurczak z ryżem", "servings": 2, "source": "generated",
            "ingredients": [
                {"name": "pierś z kurczaka", "amount": "300 g", "grams": 300, "kcal": 360, "protein_g": 69, "carbs_g": 0, "fat_g": 6},
                {"name": "ryż", "grams": 200, "kcal": 700, "protein_g": 14, "carbs_g": 156, "fat_g": 2},
                {"name": "  ", "kcal": 99},
            ],
            "steps": "Ugotuj ryż.\n\nUsmaż kurczaka.",
            **extra,
        })

    def test_recipe_derives_per_serving_from_ingredients(self):
        recipe = self._recipe()
        self.assertEqual(len(recipe["ingredients"]), 2)
        self.assertEqual(recipe["steps"], ["Ugotuj ryż.", "Usmaż kurczaka."])
        self.assertEqual(recipe["per_serving"], {"kcal": 530.0, "protein_g": 41.5, "carbs_g": 78.0, "fat_g": 4.0})
        with self.assertRaises(HTTPException):
            recipes.create_recipe(self.conn, {"title": " "})

    def test_planning_a_recipe_and_logging_portions(self):
        recipe = self._recipe()
        week = dinner_plan.set_dinner(self.conn, "2026-10-06", {"recipe_id": recipe["id"], "servings": 1.5})
        tuesday = week["days"][1]
        self.assertEqual((tuesday["dish"], tuesday["kcal"], tuesday["recipe"]["id"]), ("Kurczak z ryżem", 795.0, recipe["id"]))
        self.assertEqual(tuesday["recipe"]["ingredients"], ["ryż", "pierś z kurczaka"])
        self.assertEqual(tuesday["recipe"]["carbs_g"], 117.0)
        items = dinner_plan.dinner_log_items(self.conn, "2026-10-06")["items"]
        self.assertEqual([(item["grams"], item["kcal"]) for item in items], [(225.0, 270.0), (150.0, 525.0)])
        self.assertEqual(recipes.list_recipes(self.conn)[0]["planned_count"], 1)

    def test_editing_a_recipe_updates_planned_dinners_and_delete_keeps_the_dish(self):
        recipe = self._recipe()
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"recipe_id": recipe["id"]})
        recipes.update_recipe(self.conn, recipe["id"], {**recipe, "title": "Kurczak z ryżem basmati", "servings": 4})
        tuesday = dinner_plan.build_dinner_week(self.conn, MONDAY)["days"][1]
        self.assertEqual((tuesday["dish"], tuesday["kcal"]), ("Kurczak z ryżem basmati", 265.0))
        recipes.delete_recipe(self.conn, recipe["id"])
        tuesday = dinner_plan.build_dinner_week(self.conn, MONDAY)["days"][1]
        self.assertEqual((tuesday["dish"], tuesday["recipe"]), ("Kurczak z ryżem basmati", None))

    def test_plain_dish_logs_as_one_item_when_kcal_known(self):
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": "Kebab", "kcal": 900, "protein_g": 40})
        self.assertEqual(dinner_plan.dinner_log_items(self.conn, "2026-10-06")["items"][0]["kcal"], 900)
        dinner_plan.set_dinner(self.conn, "2026-10-07", {"dish": "Zupa"})
        self.assertEqual(dinner_plan.dinner_log_items(self.conn, "2026-10-07")["items"], [])


    def _shopping_recipe(self, title, ingredients, servings=2):
        return recipes.create_recipe(self.conn, {"title": title, "servings": servings, "ingredients": ingredients})

    def test_shopping_list_scales_portions_and_sums_matching_items(self):
        curry = self._shopping_recipe("Curry", [
            {"name": "Pierś z kurczaka", "amount": "300 g", "grams": 300},
            {"name": "ryż", "grams": 200, "product_id": 7, "per_100g": {"kcal": 350}},
        ])
        bowl = self._shopping_recipe("Bowl", [
            {"name": "  pierś  z kurczaka.", "grams": 100},
            {"name": "ryż", "grams": 100, "product_id": 7, "per_100g": {"kcal": 350}},
        ], servings=1)
        dinner_plan.set_dinner(self.conn, "2026-10-05", {"recipe_id": curry["id"], "servings": 1})
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"recipe_id": bowl["id"], "servings": 2})
        dinner_plan.set_dinner(self.conn, "2026-10-07", {"recipe_id": curry["id"], "servings": 2})
        only_monday = dinner_plan.shopping_list(self.conn, ["2026-10-05"])
        self.assertEqual([(item["name"], item["grams"]) for item in only_monday["items"]], [("Pierś z kurczaka", 150.0), ("ryż", 100.0)])
        result = dinner_plan.shopping_list(self.conn, ["2026-10-06", "2026-10-05"])
        self.assertEqual(result["dates"], ["2026-10-05", "2026-10-06"])
        self.assertEqual([(item["key"], item["grams"]) for item in result["items"]],
                         [("name:pierś z kurczaka", 350.0), ("product:7", 300.0)])
        self.assertEqual([source["date"] for source in result["items"][0]["sources"]], ["2026-10-05", "2026-10-06"])
        self.assertEqual(result["review"], [])

    def test_shopping_list_keeps_distinct_products_and_unlinked_names_apart(self):
        recipe = self._shopping_recipe("Owsianka", [
            {"name": "jogurt", "grams": 150, "product_id": 1, "per_100g": {"kcal": 60}},
            {"name": "jogurt", "grams": 150, "product_id": 2, "per_100g": {"kcal": 90}},
            {"name": "jogurt", "grams": 50},
            {"name": "jogurty", "grams": 50},
        ], servings=1)
        dinner_plan.set_dinner(self.conn, "2026-10-05", {"recipe_id": recipe["id"]})
        keys = [item["key"] for item in dinner_plan.shopping_list(self.conn, ["2026-10-05"])["items"]]
        self.assertEqual(sorted(keys), ["name:jogurt", "name:jogurty", "product:1", "product:2"])

    def test_shopping_list_sends_unmeasured_items_and_plain_dinners_to_review(self):
        recipe = self._shopping_recipe("Zupa", [
            {"name": "marchew", "amount": "2 szt."},
            {"name": "sól", "amount": "do smaku", "grams": 0},
            {"name": "bulion", "grams": 500},
        ])
        dinner_plan.set_dinner(self.conn, "2026-10-05", {"recipe_id": recipe["id"]})
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"dish": "Kebab", "kcal": 900})
        result = dinner_plan.shopping_list(self.conn, ["2026-10-05", "2026-10-06", "2026-10-07"])
        self.assertEqual([(item["name"], item["grams"]) for item in result["items"]], [("bulion", 250.0)])
        self.assertEqual([(item["dish"], item["name"], item["amount"], item["reason"]) for item in result["review"]], [
            ("Zupa", "marchew", "2 szt.", "no_grams"),
            ("Zupa", "sól", "do smaku", "no_grams"),
            ("Kebab", None, None, "no_recipe"),
        ])
        self.assertEqual([dinner["date"] for dinner in result["dinners"]], ["2026-10-05", "2026-10-06"])

    def test_shopping_list_is_read_only_and_follows_portion_changes(self):
        recipe = self._recipe()
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"recipe_id": recipe["id"], "servings": 1})
        snapshot = lambda: [list(map(tuple, self.conn.execute(f"SELECT * FROM {table}").fetchall()))
                            for table in ("dinner_plans", "recipes", "food_entries")]
        before = snapshot()
        first = dinner_plan.shopping_list(self.conn, ["2026-10-06"])
        self.assertEqual(snapshot(), before)
        self.assertEqual(first["items"][0]["grams"], 150.0)
        dinner_plan.set_dinner(self.conn, "2026-10-06", {"recipe_id": recipe["id"], "servings": 3})
        self.assertEqual(dinner_plan.shopping_list(self.conn, ["2026-10-06"])["items"][0]["grams"], 450.0)
        self.assertEqual(dinner_plan.shopping_list(self.conn, [])["items"], [])
        with self.assertRaises(HTTPException):
            dinner_plan.shopping_list(self.conn, ["2026-13-01"])


if __name__ == "__main__":
    unittest.main()
