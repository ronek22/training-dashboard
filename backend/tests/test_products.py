import sqlite3
import unittest

import httpx
from fastapi import HTTPException

from backend.app.services import products, recipes

HITS = [
    {"code": "5906712825328", "product_name": "Frankfurterki wędzone", "brands": ["Sokołów"],
     "nutriments": {"energy-kcal_100g": 292, "proteins_100g": 16, "carbohydrates_100g": 0.8, "fat_100g": 25}},
    {"code": "20859237", "product_name": "Frankfurterki z szynki", "brands": ["Pikok Pure Lidl"], "serving_size": "42g",
     "quantity": "0,45 kg", "nutriments": {"energy-kj_100g": 965, "proteins_100g": 18.5, "carbohydrates_100g": 0.4, "fat_100g": 17.4}},
    {"code": "1", "product_name": "Kiełbasa śląska", "brands": ["Pikok"], "nutriments": {}},
    {"code": "2", "product_name": "Masło", "brands": ["Pilos"], "nutriments": {"energy-kcal_100g": 740}},
]


def transport(request: httpx.Request) -> httpx.Response:
    if "/api/v2/product/20859237" in str(request.url):
        return httpx.Response(200, json={"product": HITS[1]})
    if "/api/v2/product/" in str(request.url):
        return httpx.Response(404, json={"status": 0})
    assert 'countries_tags:"en:poland"' in request.url.params["q"]
    return httpx.Response(200, json={"hits": HITS})


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, brand TEXT, barcode TEXT UNIQUE,
            kcal REAL NOT NULL DEFAULT 0, protein_g REAL NOT NULL DEFAULT 0, carbs_g REAL NOT NULL DEFAULT 0,
            fat_g REAL NOT NULL DEFAULT 0, serving_g REAL, package_g REAL, source TEXT NOT NULL DEFAULT 'manual',
            use_count INTEGER NOT NULL DEFAULT 0, created_at TEXT)"""
        )
        self.client = httpx.Client(transport=httpx.MockTransport(transport))

    def test_search_ranks_by_query_words_and_skips_products_without_energy(self):
        found = products.search_off("frankfurterki pikok", self.client)
        self.assertEqual([p["barcode"] for p in found], ["20859237", "5906712825328"])
        pikok = found[0]
        self.assertEqual(pikok["per_100g"]["kcal"], 230.6)
        self.assertEqual((pikok["serving_g"], pikok["package_g"]), (42.0, 450.0))
        self.assertEqual(pikok["brand"], "Pikok Pure Lidl")
        self.assertEqual([p["exact"] for p in found], [True, False])

    def test_barcode_lookup(self):
        self.assertEqual(products.search_off("20859237", self.client)[0]["name"], "Frankfurterki z szynki")
        self.assertEqual(products.search_off("12345678", self.client), [])

    def test_save_upserts_by_barcode_and_local_search_ignores_diacritics(self):
        payload = {"name": "Frankfurterki z jagnięciną", "brand": "Pikok", "barcode": "20123456", "source": "label",
                   "per_100g": {"kcal": 250, "protein_g": 14, "carbs_g": 1, "fat_g": 21}, "serving_g": 50}
        first = products.save_product(self.conn, payload)
        again = products.save_product(self.conn, {**payload, "per_100g": {**payload["per_100g"], "kcal": 255}})
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(again["per_100g"]["kcal"], 255)
        self.assertEqual(len(products.list_products(self.conn, "jagniecina pikok")), 1)
        self.assertEqual(products.list_products(self.conn, "skyr"), [])
        self.assertEqual(products.products_hint(self.conn)[0]["name"], "Frankfurterki z jagnięciną (Pikok)")

    def test_validation(self):
        with self.assertRaises(HTTPException):
            products.save_product(self.conn, {"name": "X", "per_100g": {}})
        with self.assertRaises(HTTPException):
            products.save_product(self.conn, {"name": "X", "barcode": "12ab", "per_100g": {"kcal": 100}})

    def test_recipe_ingredient_keeps_product_link(self):
        cleaned = recipes._clean_ingredients([
            {"name": "frankfurterki", "grams": 100, "kcal": 250, "product_id": 3, "per_100g": {"kcal": 250, "protein_g": "14"}},
            {"name": "bułka", "per_100g": {"kcal": 1}},
        ])
        self.assertEqual(cleaned[0]["per_100g"], {"kcal": 250.0, "protein_g": 14.0, "carbs_g": 0.0, "fat_g": 0.0})
        self.assertNotIn("per_100g", cleaned[1])


if __name__ == "__main__":
    unittest.main()
