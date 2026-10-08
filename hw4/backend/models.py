"""Pydantic types shared by the API, the agent and its tools."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


# --- auth -------------------------------------------------------------------
class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# --- chat -------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    product_id: str | None = Field(default=None, max_length=200)  # product page the shopper is on, if any


StockStatus = Literal["in_stock", "low_stock", "sold_out"]


class SizeStock(BaseModel):
    size: str
    quantity: int
    sold_out: bool
    status: StockStatus  # in_stock (>5), low_stock (1-5), sold_out (0)


class ProductCard(BaseModel):
    """A product card for the page, built on the server from rows a tool returned (never from model text)."""
    product_id: str
    name: str
    price: float
    image_url: str
    garment_type: str
    short_description: str
    total_stock: int
    sizes: list[SizeStock]


class ChatReply(BaseModel):
    reply: str
    model: str
    products: list[ProductCard] = []


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = []
    model: str | None = None
    created_at: str


@dataclass
class AgentDeps:
    """Per-run state handed to the agent's tools and dynamic prompts."""
    user_id: int | None = None  # from the session token only
    user_name: str | None = None
    user_email: str | None = None
    page_product_id: str | None = None  # product page the shopper is viewing
    page_product_name: str | None = None
    found_rows: dict[str, dict] = field(default_factory=dict)  # product_id -> catalogue row the search tool returned


# --- tool results -----------------------------------------------------------
LookupStatus = Literal["found", "multiple_matches", "not_found"]


class ProductOption(BaseModel):
    """A candidate when a name matches several products, so the agent can ask which one."""
    product_id: str
    name: str
    garment_type: str
    price: float


class LookupResult(BaseModel):
    """Fields every product lookup returns."""
    status: LookupStatus
    query: str
    product_id: str | None = None
    name: str | None = None
    options: list[ProductOption] = []
    message: str


class DescriptionResult(LookupResult):
    garment_type: str | None = None
    description: str | None = None
    colors: list[str] = []


class PriceResult(LookupResult):
    price: float | None = None
    price_display: str | None = None


class StockResult(LookupResult):
    requested_size: str | None = None
    requested_size_stock: SizeStock | None = None
    sizes: list[SizeStock] = []
    sold_out_sizes: list[str] = []
    total_stock: int | None = None


class SearchHit(BaseModel):
    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    total_stock: int
    size_stock: int | None = None  # units in the size the search filtered on, if any


class SearchResult(BaseModel):
    query: str
    max_price: float | None = None
    size: str | None = None
    total_matches: int
    products: list[SearchHit]
    message: str


class SimilarItemsResult(LookupResult):
    size: str | None = None
    alternatives: list[SearchHit] = []


# --- audit trail ------------------------------------------------------------
class AuditEntry(BaseModel):
    """One row in output/audit_trail.json: a tool call, or the end of an agent run. Never holds emails,
    passwords or full message text: args and results are short summaries."""
    timestamp: str
    run_id: str
    event: Literal["tool_call", "run_end"]
    model: str
    tool: str | None = None
    args: str | None = None
    result: str | None = None
    stop_reason: Literal["final answer", "usage limit", "error"] | None = None
    tool_calls: int | None = None
