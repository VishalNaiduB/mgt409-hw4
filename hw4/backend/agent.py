"""Campus Customs chat agent: loads prompts/prompt.md and the Portkey-routed OpenAI models, wires up tools."""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import find_dotenv, load_dotenv
from openai import AsyncOpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart,
                                  ToolReturnPart, UserPromptPart)
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

import tools
from models import AgentDeps, AuditEntry

load_dotenv(find_dotenv())

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompts" / "prompt.md"
AUDIT_PATH = HERE.parent / "output" / "audit_trail.json"
_AUDIT_LOCK = threading.Lock()
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")

MODEL = os.getenv("MODEL", "gpt-5.6-luna")
HARD_MODEL = os.getenv("HARD_MODEL", "gpt-6-astra")
MAX_REQUESTS = 6
MAX_TOOL_CALLS = 8
LIMIT_REPLY = "Sorry, that question needed more steps than I'm allowed. Could you ask it in a simpler way?"
FILTERED_REPLY = "I can only help with Campus Customs shopping. Ask me about our Yale gear, sizes, prices or stock!"


COMPLEX_WORDS = ("compare", "comparison", "difference", " vs", "versus", "better", "recommend", "suggest", "gift",
                 "present", "outfit", "similar", "alternative", "instead", "matching", "match with", "budget",
                 "which one", "which should", "help me choose", "help me pick", "both", "each of")
CONSTRAINTS = {
    "price": re.compile(r"\$\s?\d|\bunder\b|\bbelow\b|\bcheap|\bless than\b|\bbudget\b"),
    "size": re.compile(r"\b(xxl|xl|xs|small|medium|large|size [smlx]+)\b"),
    "colour": re.compile(r"\b(navy|blue|white|gr[ae]y|black|red|pink|green|maroon|heather|cream|yellow)\b"),
}


def route_model(message: str) -> str:
    """gpt-5.6-luna for simple lookups; gpt-6-astra for harder multi-step questions."""
    text = f" {message.lower()} "
    hard = (
        len(message) > 220
        or message.count("?") >= 2
        or any(w in text for w in COMPLEX_WORDS)
        or sum(bool(rx.search(text)) for rx in CONSTRAINTS.values()) >= 2
    )
    return HARD_MODEL if hard else MODEL


@lru_cache(maxsize=1)
def client() -> AsyncOpenAI:
    """AsyncOpenAI client pointed at Yale's Portkey gateway (same setup as HW3)."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to a .env file (see .env.example).")
    header_kwargs: dict[str, str] = {"api_key": api_key}
    for env_name, arg in (("PORTKEY_VIRTUAL_KEY", "virtual_key"),
                          ("PORTKEY_PROVIDER", "provider"),
                          ("PORTKEY_CONFIG", "config")):
        if os.getenv(env_name):
            header_kwargs[arg] = os.getenv(env_name)
    return AsyncOpenAI(
        base_url=os.getenv("PORTKEY_BASE_URL", PORTKEY_GATEWAY_URL),
        api_key=api_key,
        default_headers=createHeaders(**header_kwargs),
        timeout=float(os.getenv("REQUEST_TIMEOUT", "60")),
        max_retries=1,
    )


@lru_cache(maxsize=4)
def chat_model(name: str) -> OpenAIChatModel | OpenAIResponsesModel:
    """gpt-6-astra uses the Responses API: on Chat Completions the gateway rejects tools while it reasons."""
    provider = OpenAIProvider(openai_client=client())
    if name == HARD_MODEL:
        return OpenAIResponsesModel(name, provider=provider)
    return OpenAIChatModel(name, provider=provider)


agent = Agent(deps_type=AgentDeps, tools=tools.TOOLS)


@agent.instructions
def system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Read prompt.md on every run so prompt edits apply without a restart."""
    return PROMPT_PATH.read_text(encoding="utf-8")


@agent.instructions
def customer_and_page(ctx: RunContext[AgentDeps]) -> str:
    """Dynamic context: who the shopper is (from the session token) and which product page they are on."""
    d = ctx.deps
    if d.user_id is not None:
        who = (f"The shopper is logged in as {d.user_name} (email: {d.user_email}). Use their first name when it "
               "feels natural. These are their own details; you may confirm them to them, but never anyone else's.")
    else:
        who = "The shopper is a guest (not logged in). You don't know their name; don't guess it."
    if d.page_product_id:
        page = (f"The shopper is currently viewing the product page for \"{d.page_product_name}\" "
                f"(product id: {d.page_product_id}). If they say \"this\", \"it\" or \"this one\" without naming "
                "a product, they mean this product: pass its product id to the tools.")
    else:
        page = "The shopper is not on a product page right now."
    return f"## Current shopper\n\n{who}\n\n## Page context\n\n{page}"


def history_to_messages(rows: list[tuple[str, str]]) -> list[ModelMessage]:
    """Saved (role, content) rows as PydanticAI message history."""
    messages: list[ModelMessage] = []
    for role, content in rows:
        if role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=content)]))
    while messages and isinstance(messages[0], ModelResponse):  # history must start with the shopper's turn
        messages.pop(0)
    return messages


def _short(value: object, limit: int = 160) -> str:
    """One-line summary for the audit trail, with anything that looks like an email address removed."""
    if isinstance(value, BaseModel):
        d = value.model_dump()
        keep = ("status", "product_id", "name", "total_matches", "requested_size", "price_display", "message")
        value = {k: d[k] for k in keep if d.get(k) not in (None, "", [])}
        if "products" in d:
            value["shown"] = [p["product_id"] for p in d["products"]]
        if "alternatives" in d:
            value["alternatives"] = [p["product_id"] for p in d["alternatives"]]
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = EMAIL_RE.sub("[email]", " ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def append_audit(entries: list[AuditEntry]) -> None:
    """Append to output/audit_trail.json: read, append, write a temp file, then atomically rename.

    The file only ever grows. If it exists but is not a valid JSON array, nothing is written (so it is never wiped).
    """
    if not entries:
        return
    with _AUDIT_LOCK:
        rows: list = []
        if AUDIT_PATH.exists():
            try:
                rows = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
            except json.JSONDecodeError:
                rows = None
            if not isinstance(rows, list):
                print(f"[audit] {AUDIT_PATH} is not a JSON array; skipping write so it is not overwritten", flush=True)
                return
        rows.extend(e.model_dump() for e in entries)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_name(AUDIT_PATH.name + ".tmp")
        tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tool_entries(messages: list[ModelMessage], run_id: str, model_name: str) -> list[AuditEntry]:
    """One entry per tool call in this run, paired with its result."""
    returns = {p.tool_call_id: p for m in messages for p in m.parts if isinstance(p, (ToolReturnPart, RetryPromptPart))}
    entries = []
    for m in messages:
        for part in m.parts:
            if not isinstance(part, ToolCallPart):
                continue
            ret = returns.get(part.tool_call_id)
            if isinstance(ret, ToolReturnPart):
                result, when = _short(ret.content), ret.timestamp.isoformat(timespec="seconds")
            elif isinstance(ret, RetryPromptPart):
                result, when = _short(f"rejected, retry: {ret.content}"), ret.timestamp.isoformat(timespec="seconds")
            else:
                result, when = "no result (run stopped)", _now()
            entries.append(AuditEntry(timestamp=when, run_id=run_id, event="tool_call", model=model_name,
                                      tool=part.tool_name, args=_short(part.args_as_dict(), 120), result=result))
    return entries


async def _run_once(message: str, deps: AgentDeps, model_name: str, history: list[ModelMessage] | None) -> str:
    """One capped, audited agent run. Raises on model/API errors (after auditing them)."""
    limits = UsageLimits(request_limit=MAX_REQUESTS, tool_calls_limit=MAX_TOOL_CALLS)
    run_id = uuid.uuid4().hex[:12]
    messages: list[ModelMessage] = []
    usage: RunUsage | None = None
    stop, detail, reply = "error", None, None
    try:
        async with agent.iter(message, deps=deps, model=chat_model(model_name), usage_limits=limits,
                              message_history=history or None) as run:
            try:
                async for _ in run:
                    pass
            finally:
                messages = run.new_messages()
                usage = run.usage
            reply = run.result.output
        stop = "final answer"
    except UsageLimitExceeded as exc:
        stop, detail, reply = "usage limit", _short(str(exc)), LIMIT_REPLY
        print(f"[agent] usage limit hit: {exc}", flush=True)
    except ModelHTTPError as exc:
        if "content_filter" in str(exc.body):  # the gateway's safety filter blocked the message
            detail, reply = "ModelHTTPError 400 content_filter", FILTERED_REPLY
            print("[agent] message blocked by the provider's content filter", flush=True)
        else:
            detail = _short(f"ModelHTTPError {exc.status_code}")
            raise
    except Exception as exc:
        detail = _short(type(exc).__name__)
        raise
    finally:
        tool_entries = _tool_entries(messages, run_id, model_name)
        for e in tool_entries:
            print(f"[tool] {e.tool}({e.args}) -> {e.result}", flush=True)
        tokens = {} if usage is None else {"requests": usage.requests, "input_tokens": usage.input_tokens,
                                           "output_tokens": usage.output_tokens, "total_tokens": usage.total_tokens}
        print(f"[agent] run {run_id} {model_name} {stop}: {tokens}", flush=True)
        append_audit(tool_entries + [AuditEntry(timestamp=_now(), run_id=run_id, event="run_end", model=model_name,
                                                stop_reason=stop, result=detail, tool_calls=len(tool_entries),
                                                **tokens)])
    return reply


async def run_chat(message: str, deps: AgentDeps, model_name: str = MODEL,
                   history: list[ModelMessage] | None = None) -> tuple[str, str]:
    """Answer one shopper message; returns (reply text, model that answered).

    If the harder model fails, the question is retried once on the normal model.
    """
    try:
        return await _run_once(message, deps, model_name, history), model_name
    except ModelHTTPError as exc:
        if model_name == MODEL:
            raise
        print(f"[agent] {model_name} failed ({exc.status_code}); retrying on {MODEL}", flush=True)
        deps.found_rows.clear()
        return await _run_once(message, deps, MODEL, history), MODEL
