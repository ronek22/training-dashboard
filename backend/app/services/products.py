"""My products: packaged foods with real label values per 100 g.

Values come from Open Food Facts (searched by name or barcode), from a photo of the
label read by Claude, or are typed in. Saved products feed the food log, recipe
ingredients and Claude's meal estimates, so branded foods use real numbers.
"""
import re
import sqlite3
import unicodedata
from typing import Optional

import httpx
from fastapi import HTTPException

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")
SOURCES = ("off", "label", "manual")
OFF_SEARCH = "https://search.openfoodfacts.org/search"
OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
OFF_FIELDS = "code,product_name,product_name_pl,brands,quantity,serving_size,serving_quantity,product_quantity,nutriments,image_front_small_url"
USER_AGENT = "TrainLog/1.0 (personal training dashboard)"
BARCODE = re.compile(r"^\d{8,14}$")
NUTRIMENT_KEYS = {"kcal": "energy-kcal_100g", "protein_g": "proteins_100g", "carbs_g": "carbohydrates_100g", "fat_g": "fat_100g"}


def _fold(text: str) -> str:
    """Lowercase without Polish diacritics, so "jagnięcina" matches "jagniecina"."""
    text = unicodedata.normalize("NFKD", (text or "").lower().replace("ł", "l"))
    return "".join(char for char in text if not unicodedata.combining(char))


def _number(value, upper: float = 100000) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return min(max(0.0, round(float(value), 1)), upper)
    except (TypeError, ValueError):
        return None


def _row(row: sqlite3.Row) -> dict:
    product = dict(row)
    product["per_100g"] = {key: product.pop(key) for key in MACROS}
    return product


SELECT = "SELECT id, name, brand, barcode, kcal, protein_g, carbs_g, fat_g, serving_g, package_g, source, use_count FROM products"


def list_products(conn: sqlite3.Connection, query: str = "") -> list[dict]:
    products = [_row(row) for row in conn.execute(SELECT + " ORDER BY use_count DESC, name COLLATE NOCASE")]
    terms = _fold(query).split()
    if terms:
        products = [p for p in products if all(term in _fold(f"{p['name']} {p['brand'] or ''} {p['barcode'] or ''}") for term in terms)]
    return products


def get_product(conn: sqlite3.Connection, product_id: int) -> dict:
    row = conn.execute(SELECT + " WHERE id = ?", (product_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return _row(row)


def _values(payload: dict) -> tuple:
    name = str(payload.get("name") or "").strip()[:160]
    if not name:
        raise HTTPException(status_code=422, detail="A product needs a name.")
    source = payload.get("source") or "manual"
    if source not in SOURCES:
        raise HTTPException(status_code=422, detail="Unknown product source.")
    per_100g = payload.get("per_100g") or {}
    macros = {key: _number(per_100g.get(key), 1000 if key == "kcal" else 100) for key in MACROS}
    if macros["kcal"] is None:
        raise HTTPException(status_code=422, detail="Add at least kcal per 100 g.")
    barcode = str(payload.get("barcode") or "").strip() or None
    if barcode and not BARCODE.match(barcode):
        raise HTTPException(status_code=422, detail="A barcode is 8–14 digits.")
    return (
        name, str(payload.get("brand") or "").strip()[:80] or None, barcode,
        *(macros[key] or 0.0 for key in MACROS),
        _number(payload.get("serving_g"), 5000), _number(payload.get("package_g"), 50000), source,
    )


def save_product(conn: sqlite3.Connection, payload: dict) -> dict:
    """Insert, or refresh the product with the same barcode."""
    values = _values(payload)
    barcode = values[2]
    existing = conn.execute("SELECT id FROM products WHERE barcode = ?", (barcode,)).fetchone() if barcode else None
    if existing:
        return update_product(conn, existing["id"], payload)
    product_id = conn.execute(
        """
        INSERT INTO products (name, brand, barcode, kcal, protein_g, carbs_g, fat_g, serving_g, package_g, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    ).lastrowid
    conn.commit()
    return get_product(conn, product_id)


def update_product(conn: sqlite3.Connection, product_id: int, payload: dict) -> dict:
    updated = conn.execute(
        """
        UPDATE products SET name = ?, brand = ?, barcode = ?, kcal = ?, protein_g = ?, carbs_g = ?, fat_g = ?,
            serving_g = ?, package_g = ?, source = ? WHERE id = ?
        """,
        (*_values(payload), product_id),
    ).rowcount
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    conn.commit()
    return get_product(conn, product_id)


def delete_product(conn: sqlite3.Connection, product_id: int) -> dict:
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    return {"ok": True}


def use_product(conn: sqlite3.Connection, product_id: int) -> None:
    conn.execute("UPDATE products SET use_count = use_count + 1 WHERE id = ?", (product_id,))
    conn.commit()


# Open Food Facts

def _grams(text) -> Optional[float]:
    """Grams from a label size like "450 g", "0,5 kg" or "42g"; None for pieces or volumes."""
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", str(text or "").lower())
    if not match:
        return None
    amount = float(match.group(1).replace(",", "."))
    return round(amount * 1000 if match.group(2) == "kg" else amount, 1)


def off_product(raw: dict) -> Optional[dict]:
    nutriments = raw.get("nutriments") or {}
    per_100g = {key: _number(nutriments.get(field), 1000) for key, field in NUTRIMENT_KEYS.items()}
    if per_100g["kcal"] is None:
        kj = _number(nutriments.get("energy-kj_100g") or nutriments.get("energy_100g"), 5000)
        per_100g["kcal"] = round(kj / 4.184, 1) if kj else None
    name = (raw.get("product_name_pl") or raw.get("product_name") or "").strip()
    if not name or per_100g["kcal"] is None:
        return None
    brands = raw.get("brands")
    brand = ", ".join(brands) if isinstance(brands, list) else (brands or "")
    return {
        "name": name[:160],
        "brand": brand.strip()[:80] or None,
        "barcode": str(raw.get("code") or "") or None,
        "per_100g": {key: value or 0.0 for key, value in per_100g.items()},
        "serving_g": _number(raw.get("serving_quantity")) or _grams(raw.get("serving_size")),
        "package_g": _number(raw.get("product_quantity")) or _grams(raw.get("quantity")),
        "image": raw.get("image_front_small_url"),
        "source": "off",
    }


def rank(products: list[dict], query: str) -> list[dict]:
    """Best matches first: share of query words found in the name and brand, prefix-tolerant for Polish endings."""
    terms = [term for term in _fold(query).split() if len(term) > 1]

    def score(product: dict) -> float:
        words = _fold(f"{product['name']} {product['brand'] or ''}").replace(",", " ").split()
        hits = sum(1 for term in terms if any(word.startswith(term[:max(4, len(term) - 2)]) for word in words))
        return hits / len(terms) if terms else 0

    scored = [(score(product), index, product) for index, product in enumerate(products)]
    # "exact" tells the picker whether a product matched every word, or is only a near match.
    return [{**product, "exact": value == 1} for value, _, product in sorted(scored, key=lambda item: (-item[0], item[1])) if value > 0]


def search_off(query: str, client: Optional[httpx.Client] = None) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []
    own = client is None
    client = client or httpx.Client(timeout=15, headers={"User-Agent": USER_AGENT})
    try:
        if BARCODE.match(query):
            response = client.get(OFF_PRODUCT.format(code=query), params={"fields": OFF_FIELDS})
            if response.status_code == 404:
                return []
            response.raise_for_status()
            product = off_product(response.json().get("product") or {})
            return [{**product, "exact": True}] if product else []
        # The search ORs words, so ask for Polish products and plenty of hits, then rank them here.
        response = client.get(OFF_SEARCH, params={
            "q": f'{query} countries_tags:"en:poland"', "langs": "pl,en", "page_size": 40, "fields": OFF_FIELDS,
        })
        response.raise_for_status()
        found = [product for product in (off_product(hit) for hit in response.json().get("hits") or []) if product]
        return rank(found, query)[:10]
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Open Food Facts did not answer. Try again in a minute.") from exc
    finally:
        if own:
            client.close()


def products_hint(conn: sqlite3.Connection, limit: int = 60) -> list[dict]:
    """Compact per-100 g values for Claude's meal estimates."""
    try:
        return [
            {"name": p["name"] + (f" ({p['brand']})" if p["brand"] else ""), "per_100g": p["per_100g"], "serving_g": p["serving_g"]}
            for p in list_products(conn)[:limit]
        ]
    except sqlite3.OperationalError:
        return []
