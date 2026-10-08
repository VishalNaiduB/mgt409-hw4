"""Campus Customs API: products from the SQLite db and product images from data/products."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager, closing

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

import agent
from models import AgentDeps, ChatReply, ChatRequest, HistoryMessage, LoginRequest, SignupRequest
from tools import (IMAGES_DIR, MAX_SEARCH_RESULTS, cards_for_ids, cards_from_rows, get_conn, product_dict, size_rows,
                   sizes_by_product)

load_dotenv(find_dotenv())

SESSION_SECRET = (os.getenv("SESSION_SECRET") or secrets.token_hex(32)).encode()
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
PBKDF2_ITERATIONS = 120_000  # matches the existing users' hashes (verified against the documented test login)
MIN_PASSWORD_LENGTH = 8
BAD_LOGIN = "Email or password is incorrect."


def ensure_schema() -> None:
    """Add our own column to the existing db if a fresh copy lacks it; idempotent, runs at every startup."""
    with closing(get_conn()) as conn, conn:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "model" not in columns:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN model TEXT")  # which model answered (assistant rows)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    if not IMAGES_DIR.is_dir():
        raise RuntimeError(f"Image folder not found at {IMAGES_DIR}.")
    yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)


@app.get("/api/products")
def list_products() -> list[dict]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """SELECT c.*, COALESCE(SUM(i.quantity), 0) AS total_stock
               FROM catalogue c LEFT JOIN inventory i ON i.product_id = c.product_id
               GROUP BY c.product_id ORDER BY c.name"""
        ).fetchall()
        sizes = sizes_by_product(conn, [r["product_id"] for r in rows])
    return [{**product_dict(r), "total_stock": r["total_stock"], "sizes": [s.model_dump() for s in sizes[r["product_id"]]]}
            for r in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        sizes = size_rows(conn, product_id)
    return {**product_dict(row), "inventory": [s.model_dump() for s in sizes], "total_stock": sum(s.quantity for s in sizes)}


# --- auth -------------------------------------------------------------------
def hash_password(password: str) -> str:
    """pbkdf2_sha256$<salt>$<hex digest>, salt used as plain text: the format already in users."""
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return hmac.compare_digest(candidate, digest)


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def _sign(payload: str) -> str:
    digest = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def make_token(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time()) + SESSION_TTL_SECONDS}"
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    """User id from a valid, unexpired token, else None."""
    try:
        user_id, expires, signature = token.split(".")
        if not hmac.compare_digest(_sign(f"{user_id}.{expires}"), signature) or int(expires) < time.time():
            return None
        return int(user_id)
    except (ValueError, AttributeError):
        return None


def public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "first_name": row["first_name"],
            "last_name": row["last_name"], "email": row["email"]}


def current_user(authorization: str | None) -> dict | None:
    """The logged-in user, worked out only from the signed token in the Authorization header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    user_id = read_token(authorization.split(" ", 1)[1].strip())
    if user_id is None:
        return None
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


@app.post("/api/auth/signup")
def signup(body: SignupRequest) -> dict:
    first, last = body.first_name.strip(), body.last_name.strip()
    email = body.email.strip().lower()
    if not first or not last:
        raise HTTPException(400, "Please enter your first and last name.")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(400, "Please enter a valid email address.")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    with closing(get_conn()) as conn, conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists. Please log in instead.")
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
                (f"{first} {last}", email, hash_password(body.password), first, last),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with that email already exists. Please log in instead.")
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"token": make_token(row["id"]), "user": public_user(row)}


@app.post("/api/auth/login")
def login(body: LoginRequest) -> dict:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (body.email.strip().lower(),)).fetchone()
    if row is None:
        verify_password(body.password, _DUMMY_HASH)  # same work either way, so timing doesn't reveal accounts
        raise HTTPException(401, BAD_LOGIN)
    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, BAD_LOGIN)
    return {"token": make_token(row["id"]), "user": public_user(row)}


@app.get("/api/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    return user


# --- chat -------------------------------------------------------------------
HISTORY_FOR_AGENT = 20  # most recent saved messages the agent sees
HISTORY_FOR_PANEL = 50  # most recent saved messages the chat panel shows


def saved_product_ids(products_json: str | None) -> list[str]:
    """Product ids from products_json: new rows store ids; older rows stored full product snapshots."""
    try:
        items = json.loads(products_json) if products_json else []
    except json.JSONDecodeError:
        return []
    ids = [i if isinstance(i, str) else i.get("product_id") for i in items if isinstance(i, (str, dict))]
    return [i for i in ids if i]


def recent_messages(conn, user_id: int, limit: int) -> list:
    rows = conn.execute(
        "SELECT role, content, products_json, model, created_at FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return rows[::-1]


def page_product(product_id: str | None) -> tuple[str | None, str | None]:
    """(id, name) of the product page the shopper is on, if it is a real product."""
    if not product_id:
        return None, None
    with closing(get_conn(readonly=True)) as conn:
        row = conn.execute("SELECT product_id, name FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    return (row["product_id"], row["name"]) if row else (None, None)


@app.post("/api/chat")
async def chat(body: ChatRequest, authorization: str | None = Header(default=None)) -> ChatReply:
    user = current_user(authorization)
    page_id, page_name = page_product(body.product_id)
    deps = AgentDeps(page_product_id=page_id, page_product_name=page_name)
    history = []
    if user:
        deps.user_id, deps.user_name, deps.user_email = user["id"], user["name"], user["email"]
        with closing(get_conn(readonly=True)) as conn:
            saved = recent_messages(conn, user["id"], HISTORY_FOR_AGENT)
        history = agent.history_to_messages([(r["role"], r["content"]) for r in saved])
    model_name = agent.route_model(body.message)
    try:
        reply, model_name = await agent.run_chat(body.message, deps, model_name, history)
    except Exception as exc:
        print(f"[chat] agent error: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(502, "The assistant is having trouble right now. Please try again in a moment.")
    cards = cards_from_rows(list(deps.found_rows.values())[:MAX_SEARCH_RESULTS])
    if user:
        with closing(get_conn()) as conn, conn:
            conn.execute("INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'user', ?, NULL)",
                         (user["id"], body.message))
            conn.execute("INSERT INTO chat_messages (user_id, role, content, products_json, model) "
                         "VALUES (?, 'assistant', ?, ?, ?)",
                         (user["id"], reply, json.dumps([c.product_id for c in cards]), model_name))
    return ChatReply(reply=reply, model=model_name, products=cards)


@app.get("/api/chat/history")
def chat_history(authorization: str | None = Header(default=None)) -> list[HistoryMessage]:
    """The logged-in shopper's own saved chat, with cards rebuilt from the current catalogue and inventory."""
    user = current_user(authorization)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    with closing(get_conn(readonly=True)) as conn:
        rows = recent_messages(conn, user["id"], HISTORY_FOR_PANEL)
        return [HistoryMessage(role=r["role"], content=r["content"], created_at=r["created_at"], model=r["model"],
                               products=cards_for_ids(conn, saved_product_ids(r["products_json"])))
                for r in rows if r["role"] in ("user", "assistant")]

app.mount("/media/products", StaticFiles(directory=IMAGES_DIR, check_dir=False), name="product-images")

