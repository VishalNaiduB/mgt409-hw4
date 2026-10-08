"""Database access and the tools the Campus Customs agent can call. Each tool returns a typed result from models.py."""

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic_ai import RunContext

from models import (AgentDeps, DescriptionResult, PriceResult, ProductCard, ProductOption, SearchHit, SearchResult,
                    SimilarItemsResult, SizeStock, StockResult)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
IMAGES_DIR = DATA_DIR / "products"

SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
SIZE_ORDER = "CASE size WHEN 'XS' THEN 0 WHEN 'S' THEN 1 WHEN 'M' THEN 2 WHEN 'L' THEN 3 WHEN 'XL' THEN 4 WHEN 'XXL' THEN 5 ELSE 6 END"
SIZE_ALIASES = {
    "xs": "XS", "extra small": "XS", "x-small": "XS", "xsmall": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "extra large": "XL", "x-large": "XL", "xlarge": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "extra extra large": "XXL", "double xl": "XXL",
}
TERM_SYNONYMS = {"tee": "t-shirt", "tees": "t-shirt", "tshirt": "t-shirt", "tshirts": "t-shirt", "hoody": "hoodie",
                 "quarterzip": "quarter-zip", "crew": "crewneck", "sweater": "sweat"}
STOP_WORDS = {"a", "an", "the", "do", "you", "have", "any", "your", "with", "of", "in", "for", "and", "me", "show", "what", "is", "are"}
MAX_OPTIONS = 8
MAX_SEARCH_RESULTS = 12
MAX_SIMILAR = 4
LOW_STOCK = 5  # 1-5 units left counts as low stock
TOTAL_STOCK_SQL = "(SELECT COALESCE(SUM(i.quantity), 0) FROM inventory i WHERE i.product_id = catalogue.product_id) AS total_stock"


def get_conn(readonly: bool = False) -> sqlite3.Connection:
    """Open the existing db (never create it) with foreign keys enforced."""
    if not DB_PATH.is_file():
        raise RuntimeError(f"Database not found at {DB_PATH}. Put campus_customs.db in the data/ folder.")
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode={'ro' if readonly else 'rw'}", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def image_url(image_file_path: str) -> str:
    """image_file_path is relative to data/, served under /media/ (same pattern as old chat history)."""
    return f"/media/{image_file_path}"


def product_dict(row: sqlite3.Row) -> dict:
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"]),
        "search_tags": json.loads(row["search_tags"]),
        "image_file_path": row["image_file_path"],
        "image_url": image_url(row["image_file_path"]),
        "price": row["price"],
    }


def size_stock(size: str, quantity: int) -> SizeStock:
    status = "sold_out" if quantity <= 0 else "low_stock" if quantity <= LOW_STOCK else "in_stock"
    return SizeStock(size=size, quantity=quantity, sold_out=quantity <= 0, status=status)


def size_rows(conn: sqlite3.Connection, product_id: str) -> list[SizeStock]:
    rows = conn.execute(
        f"SELECT size, quantity FROM inventory WHERE product_id = ? ORDER BY {SIZE_ORDER}", (product_id,)
    ).fetchall()
    return [size_stock(r["size"], r["quantity"]) for r in rows]


def sizes_by_product(conn: sqlite3.Connection, product_ids: list[str]) -> dict[str, list[SizeStock]]:
    """Per-size stock for many products in one query."""
    out: dict[str, list[SizeStock]] = {pid: [] for pid in product_ids}
    if not product_ids:
        return out
    marks = ",".join("?" * len(product_ids))
    for r in conn.execute(f"SELECT product_id, size, quantity FROM inventory WHERE product_id IN ({marks}) "
                          f"ORDER BY product_id, {SIZE_ORDER}", product_ids):
        out[r["product_id"]].append(size_stock(r["size"], r["quantity"]))
    return out


def search_terms(text: str) -> list[str]:
    """Lower-cased words to match, with plurals trimmed and common shop synonyms mapped."""
    words = re.findall(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", text.lower())
    terms = []
    for w in words:
        if w in STOP_WORDS:
            continue
        w = TERM_SYNONYMS.get(w, w)
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        terms.append(w)
    return terms


def match_products(conn: sqlite3.Connection, text: str, max_price: float | None = None,
                   size: str | None = None) -> list[sqlite3.Row]:
    """Products where every term appears (case-insensitively) in name, garment_type, search_tags or description.

    Optional filters: price at or under max_price, and at least one unit in stock in size (a normalized size code).
    With no terms, the filters alone decide; with no terms and no filters, nothing matches.
    """
    terms = search_terms(text)
    if not terms and max_price is None and size is None:
        return []
    clauses = ["(lower(name) LIKE ? OR lower(garment_type) LIKE ? OR lower(search_tags) LIKE ? OR lower(description) LIKE ?)"
               for _ in terms]
    params: list = [f"%{t}%" for t in terms for _ in range(4)]
    if max_price is not None:
        clauses.append("price <= ?")
        params.append(max_price)
    size_col = "NULL AS size_stock"
    if size is not None:
        clauses.append("EXISTS (SELECT 1 FROM inventory i WHERE i.product_id = catalogue.product_id AND i.size = ? AND i.quantity > 0)")
        params.append(size)
        size_col = "(SELECT i.quantity FROM inventory i WHERE i.product_id = catalogue.product_id AND i.size = ?) AS size_stock"
        params.insert(0, size)
    where = " AND ".join(clauses) or "1"
    return conn.execute(f"SELECT *, {TOTAL_STOCK_SQL}, {size_col} FROM catalogue WHERE {where} ORDER BY name",
                        params).fetchall()


def resolve_product(conn: sqlite3.Connection, query: str) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    """(product, []) for a single match, (None, candidates) otherwise. Accepts a product id or a name."""
    q = query.strip()
    row = conn.execute(
        "SELECT * FROM catalogue WHERE lower(product_id) = lower(?) OR lower(name) = lower(?)", (q, q)
    ).fetchone()
    if row:
        return row, []
    candidates = match_products(conn, q)
    if len(candidates) == 1:
        return candidates[0], []
    terms = search_terms(q)
    in_name = [r for r in candidates if all(t in r["name"].lower() for t in terms)]
    if len(in_name) == 1:
        return in_name[0], []
    return None, candidates


def _options(rows: list[sqlite3.Row]) -> list[ProductOption]:
    return [ProductOption(product_id=r["product_id"], name=r["name"], garment_type=r["garment_type"], price=r["price"])
            for r in rows[:MAX_OPTIONS]]


def _no_single_match(query: str, candidates: list[sqlite3.Row]) -> dict:
    if not candidates:
        return {"status": "not_found", "query": query,
                "message": f"No product matches '{query}'. Do not guess; tell the shopper we couldn't find it."}
    more = f" (showing {MAX_OPTIONS} of {len(candidates)})" if len(candidates) > MAX_OPTIONS else ""
    return {"status": "multiple_matches", "query": query, "options": _options(candidates),
            "message": f"'{query}' matches {len(candidates)} products{more}. Ask the shopper which one they mean."}


def normalize_size(size: str) -> str | None:
    return SIZE_ALIASES.get(size.strip().lower().replace("size ", ""))


def get_product_description(product: str) -> DescriptionResult:
    """Look up a product's description, garment type and colours.

    Args:
        product: the product id (e.g. "basic-hoodie-big-yale") or its name / a few words from it.
    """
    with closing(get_conn(readonly=True)) as conn:
        row, candidates = resolve_product(conn, product)
    if row is None:
        return DescriptionResult(**_no_single_match(product, candidates))
    return DescriptionResult(
        status="found", query=product, product_id=row["product_id"], name=row["name"],
        garment_type=row["garment_type"], description=row["description"], colors=json.loads(row["colors"]),
        message="Found.",
    )


def get_product_price(product: str) -> PriceResult:
    """Look up a product's current price in US dollars.

    Args:
        product: the product id or its name / a few words from it.
    """
    with closing(get_conn(readonly=True)) as conn:
        row, candidates = resolve_product(conn, product)
    if row is None:
        return PriceResult(**_no_single_match(product, candidates))
    return PriceResult(
        status="found", query=product, product_id=row["product_id"], name=row["name"],
        price=row["price"], price_display=f"${row['price']:.2f}", message="Found.",
    )


def get_product_stock(product: str, size: str | None = None) -> StockResult:
    """Look up how many units are in stock, per size. Pass size when the shopper asks about one size.

    Args:
        product: the product id or its name / a few words from it.
        size: optional size the shopper asked about: XS, S, M, L, XL or XXL (words like "medium" work too).
    """
    with closing(get_conn(readonly=True)) as conn:
        row, candidates = resolve_product(conn, product)
        if row is None:
            return StockResult(**_no_single_match(product, candidates))
        sizes = size_rows(conn, row["product_id"])
    result = StockResult(
        status="found", query=product, product_id=row["product_id"], name=row["name"], sizes=sizes,
        sold_out_sizes=[s.size for s in sizes if s.sold_out], total_stock=sum(s.quantity for s in sizes),
        message="Found.",
    )
    if size:
        wanted = normalize_size(size)
        match = next((s for s in sizes if s.size == wanted), None)
        result.requested_size = wanted or size
        result.requested_size_stock = match
        if match is None:
            result.message = f"'{size}' is not a size we carry. Sizes are {', '.join(SIZES)}."
        elif match.sold_out:
            result.message = (f"SOLD OUT: size {match.size} of {row['name']} has 0 in stock. Say clearly it is sold "
                              "out, then call find_similar_items to offer in-stock alternatives in that size.")
        elif match.status == "low_stock":
            result.message = f"LOW STOCK: size {match.size} of {row['name']} has only {match.quantity} left."
        else:
            result.message = f"In stock: size {match.size} of {row['name']} has {match.quantity} available."
    return result


def _hit(r: sqlite3.Row) -> SearchHit:
    return SearchHit(product_id=r["product_id"], name=r["name"], garment_type=r["garment_type"], price=r["price"],
                     colors=json.loads(r["colors"]), total_stock=r["total_stock"], size_stock=r["size_stock"])


def search_products(ctx: RunContext[AgentDeps], query: str = "", max_price: float | None = None,
                    size: str | None = None) -> SearchResult:
    """Search the catalogue to show the shopper matching products as cards on the page.

    Use for browsing questions like "what hoodies do you have?", "anything for Saybrook?", "navy crewnecks",
    "gifts under $40" (max_price=40) or "what's in stock in medium?" (size="M").

    Args:
        query: 1-3 short keywords (e.g. "hoodie", "navy crewneck", "saybrook"). Every word must match.
            May be empty when max_price or size is given.
        max_price: optional budget in US dollars; only products priced at or under it are returned.
        size: optional size (XS, S, M, L, XL, XXL or words like "medium"); only products with that size in stock.
    """
    size_code = normalize_size(size) if size else None
    if size and size_code is None:
        return SearchResult(query=query, max_price=max_price, size=size, total_matches=0, products=[],
                            message=f"'{size}' is not a size we carry. Sizes are {', '.join(SIZES)}.")
    with closing(get_conn(readonly=True)) as conn:
        rows = match_products(conn, query, max_price, size_code)
    shown = rows[:MAX_SEARCH_RESULTS]
    for r in shown:
        ctx.deps.found_rows.setdefault(r["product_id"], dict(r))
    filters = "".join([f" priced at or under ${max_price:.2f}" if max_price is not None else "",
                       f" in stock in size {size_code}" if size_code else ""])
    label = f"'{query}'{filters}" if query.strip() else f"products{filters}"
    if not rows:
        message = f"No {label} found. Say so and suggest a broader search; do not invent products."
    elif len(rows) > len(shown):
        message = f"{len(rows)} {label} match; the first {len(shown)} are shown to the shopper as cards on the page."
    else:
        message = f"{len(rows)} {label} match and are shown to the shopper as cards on the page."
    return SearchResult(query=query, max_price=max_price, size=size_code, total_matches=len(rows),
                        products=[_hit(r) for r in shown], message=message)


def garment_family(garment_type: str) -> str:
    """Collapse the messy garment_type text into a few families for "similar item" matching."""
    g = garment_type.lower()
    if "quarter-zip" in g or "1/4" in g:
        return "quarter-zip"
    if "hood" in g:
        return "hoodie"
    if "jacket" in g:
        return "jacket"
    if "t-shirt" in g or "tee" in g:
        return "t-shirt"
    if "crew" in g or "sweatshirt" in g or "mockneck" in g:
        return "crewneck"
    if "shirt" in g:
        return "shirt"
    return "other"


def find_similar_items(ctx: RunContext[AgentDeps], product: str, size: str | None = None) -> SimilarItemsResult:
    """Find in-stock alternatives to a product, e.g. when it (or the shopper's size) is sold out.

    Alternatives are shown to the shopper as cards on the page.

    Args:
        product: the product id or its name / a few words from it.
        size: optional size the shopper needs; alternatives must have that size in stock.
    """
    size_code = normalize_size(size) if size else None
    with closing(get_conn(readonly=True)) as conn:
        row, candidates = resolve_product(conn, product)
        if row is None:
            return SimilarItemsResult(**_no_single_match(product, candidates))
        pool = match_products(conn, "", size=size_code) if size_code else conn.execute(
            f"SELECT *, {TOTAL_STOCK_SQL}, NULL AS size_stock FROM catalogue").fetchall()
    family = garment_family(row["garment_type"])
    tags = {t.lower() for t in json.loads(row["search_tags"])}
    colors = {c.lower() for c in json.loads(row["colors"])}

    def score(r: sqlite3.Row) -> float:
        return (10 * (garment_family(r["garment_type"]) == family)
                + 2 * len(tags & {t.lower() for t in json.loads(r["search_tags"])})
                + len(colors & {c.lower() for c in json.loads(r["colors"])})
                - abs(r["price"] - row["price"]) / 20)

    pool = [r for r in pool if r["product_id"] != row["product_id"] and r["total_stock"] > 0]
    best = sorted(pool, key=score, reverse=True)[:MAX_SIMILAR]
    for r in best:
        ctx.deps.found_rows.setdefault(r["product_id"], dict(r))
    where = f" in size {size_code}" if size_code else ""
    message = (f"{len(best)} in-stock alternatives{where} to {row['name']}, shown to the shopper as cards on the page."
               if best else f"No in-stock alternatives{where} found. Say so honestly.")
    return SimilarItemsResult(status="found", query=product, product_id=row["product_id"], name=row["name"],
                              size=size_code, alternatives=[_hit(r) for r in best], message=message)


def short_description(text: str, limit: int = 90) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind(" ")].rstrip(",.;:") + "…"


def cards_from_rows(rows: list[dict]) -> list[ProductCard]:
    """Cards built from catalogue rows a tool returned, so prices, images and stock always come from the db."""
    with closing(get_conn(readonly=True)) as conn:
        sizes = sizes_by_product(conn, [r["product_id"] for r in rows])
    return [ProductCard(product_id=r["product_id"], name=r["name"], price=r["price"],
                        image_url=image_url(r["image_file_path"]), garment_type=r["garment_type"],
                        short_description=short_description(r["description"]), total_stock=r["total_stock"],
                        sizes=sizes[r["product_id"]])
            for r in rows]


def cards_for_ids(conn: sqlite3.Connection, product_ids: list[str]) -> list[ProductCard]:
    """Cards for saved product ids, rebuilt from the current catalogue and inventory (unknown ids are skipped)."""
    if not product_ids:
        return []
    marks = ",".join("?" * len(product_ids))
    rows = {r["product_id"]: dict(r) for r in conn.execute(
        f"SELECT *, {TOTAL_STOCK_SQL} FROM catalogue WHERE product_id IN ({marks})", product_ids)}
    return cards_from_rows([rows[i] for i in product_ids if i in rows])


TOOLS = [get_product_description, get_product_price, get_product_stock, search_products, find_similar_items]
