"""Provider-agnostic LLM client.

Reads LLM_PROVIDER (anthropic|openai) and the matching key from env.
Exposes one function: chat(messages, tools=None) -> {text, tool_calls}.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# On corporate networks with TLS inspection (e.g. PwC), the intercepting root
# CA lives in the OS trust store but not in certifi, so certifi-based clients
# fail with CERTIFICATE_VERIFY_FAILED. truststore makes Python's ssl (and thus
# httpx/openai/anthropic) use the OS trust store, which already trusts that CA.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()


def _has_api_key() -> bool:
    if _PROVIDER == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    elif _PROVIDER == "openai":
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return False


def _get_anthropic_client():
    import anthropic
    key = os.environ["ANTHROPIC_API_KEY"]
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip() or None
    if base_url:
        return anthropic.Anthropic(api_key=key, base_url=base_url)
    return anthropic.Anthropic(api_key=key)


def _get_openai_client():
    """OpenAI-compatible client.

    If OPENAI_BASE_URL is set, requests are routed there instead of the
    OpenAI API — this is how NextBest talks to an OmniRoute gateway
    (e.g. http://localhost:20128/v1) or any other OpenAI-compatible proxy.
    """
    import openai
    key = os.environ["OPENAI_API_KEY"]
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    if base_url:
        return openai.OpenAI(api_key=key, base_url=base_url)
    return openai.OpenAI(api_key=key)


def embeddings_available() -> bool:
    """Dense embeddings require an OpenAI-compatible key + endpoint."""
    return _PROVIDER == "openai" and _has_api_key()


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via the OpenAI-compatible embeddings endpoint.

    Raises RuntimeError when embeddings aren't available so callers can fall
    back to the deterministic hashing retriever.
    """
    if not embeddings_available():
        raise RuntimeError("Embeddings unavailable: set an OpenAI-compatible key (LLM_PROVIDER=openai).")

    client = _get_openai_client()
    model = os.environ.get("OPENAI_EMBED_MODEL", "azure.text-embedding-3-small")
    response = client.embeddings.create(model=model, input=texts)
    # Preserve request order (OpenAI returns .data with an .index field).
    ordered = sorted(response.data, key=lambda d: d.index)
    return [list(d.embedding) for d in ordered]


def extract_json(text: str) -> dict | None:
    """Best-effort JSON parse of an LLM response.

    Gateway-routed models vary in how strictly they follow "return JSON":
    some wrap it in ```json fences, some add a sentence before/after. This
    tolerates all of those and returns None only when nothing parses.
    """
    if not text:
        return None

    candidate = text.strip()

    # Strip a leading/trailing markdown code fence if present.
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z0-9]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate).strip()

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} span and try again.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(candidate[start:end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def chat(
    messages: list[dict[str, str]],
    system: str | None = None,
    tools: list[dict] | None = None,
    temperature: float = 0.4,
    force_json: bool = False,
) -> dict[str, Any]:
    """Send a chat completion and return {text, tool_calls}.

    messages: list of {role, content}
    system: optional system prompt
    tools: optional list of tool schemas (provider-native format auto-handled)
    force_json: request a strict JSON object from the model where the provider
        supports it (OpenAI response_format). Safe to combine with extract_json.

    Falls back to deterministic mock responses when no API key is configured,
    so the pipeline can run end-to-end for demo/testing without live LLM calls.
    """
    if not _has_api_key():
        return _chat_mock(messages, system)

    if _PROVIDER == "anthropic":
        return _chat_anthropic(messages, system, tools, temperature, force_json)
    elif _PROVIDER == "openai":
        return _chat_openai(messages, system, tools, temperature, force_json)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {_PROVIDER}")


def _chat_mock(messages: list[dict], system: str | None) -> dict[str, Any]:
    """Deterministic mock for when no API key is set. Parses the user message
    to produce contextually appropriate responses for planner/draft/critique."""
    user_msg = messages[-1]["content"] if messages else ""
    system = system or ""

    if "Plan the tool calls" in user_msg:
        return _mock_planner(user_msg)
    elif "Write the outreach message" in user_msg:
        return _mock_draft(user_msg)
    elif "Score this draft" in user_msg:
        return _mock_critique(user_msg)
    elif "Answer the advisor's question" in user_msg:
        return _mock_rag(user_msg)

    return {"text": "", "tool_calls": []}


def _mock_rag(user_msg: str) -> dict[str, Any]:
    """Extractive fallback: summarise the retrieved context blocks with their
    citation tags so the copilot stays grounded even without a live LLM."""
    lines = [ln.strip() for ln in user_msg.splitlines() if ln.strip().startswith("[")]
    if not lines:
        return {"text": "I couldn't find that in your records.", "tool_calls": []}

    bullets = []
    for ln in lines[:4]:
        tag, _, body = ln.partition("] ")
        tag = tag + "]"
        body = body.split(":", 1)[-1].strip() if ":" in body else body.strip()
        bullets.append(f"- {tag} {body}")

    text = "Here's what your records show:\n" + "\n".join(bullets)
    return {"text": text, "tool_calls": []}


def _mock_planner(user_msg: str) -> dict[str, Any]:
    """Produce a plan JSON based on the scores in the user message."""
    import re
    att_match = re.search(r"Attrition risk: (\d+)", user_msg)
    ups_match = re.search(r"Upsell readiness: (\d+)", user_msg)
    att = int(att_match.group(1)) if att_match else 0
    ups = int(ups_match.group(1)) if ups_match else 0

    if att >= 50 and att >= ups:
        plan = {
            "plan": ["get_client_segment", "compute_propensity", "get_call_context", "get_market_context"],
            "framing": "re-engagement",
            "reasoning": "High attrition signals — pull call history for reconnection hook.",
        }
    elif ups >= 50:
        plan = {
            "plan": ["get_client_segment", "compute_propensity", "get_product_catalog", "get_market_context"],
            "framing": "opportunity",
            "reasoning": "Strong upsell signals — pull products and market context.",
        }
    else:
        plan = {
            "plan": ["get_client_segment", "compute_propensity", "get_call_context"],
            "framing": "check-in",
            "reasoning": "Watchlist — light check-in with call context.",
        }
    return {"text": json.dumps(plan), "tool_calls": []}


def _mock_draft(user_msg: str) -> dict[str, Any]:
    """Produce a contextual draft based on the framing and client details."""
    import re
    name_match = re.search(r"Client name: (.+)", user_msg)
    name = name_match.group(1).strip() if name_match else "there"
    first_name = name.split()[0] if name != "there" else "there"

    framing_match = re.search(r"Framing: (\w[\w-]*)", user_msg)
    framing = framing_match.group(1) if framing_match else "check-in"

    note_match = re.search(r'Recent call note: "(.+?)"', user_msg)
    note_context = note_match.group(1)[:50] if note_match else ""

    events_match = re.search(r"Life events: (.+)", user_msg)
    events = events_match.group(1).strip() if events_match else ""

    market_match = re.search(r"Market context: (.+)", user_msg)
    market = market_match.group(1)[:60] if market_match else ""

    if framing == "re-engagement":
        if "education" in note_context.lower() or "education" in events.lower():
            draft = (
                f"Hi {first_name}, I've been thinking about our last conversation regarding your "
                f"daughter's education planning. I'd love to reconnect and walk through some "
                f"options that could give you more flexibility there. Would you have 20 minutes this week?"
            )
        elif "business" in events.lower():
            draft = (
                f"Hi {first_name}, I hope things are going well with the business transition. "
                f"I've been looking at some strategies that might complement your next chapter "
                f"and would welcome the chance to catch up. Any time work for a quick call?"
            )
        else:
            draft = (
                f"Hi {first_name}, it's been a little while since we last connected and I wanted "
                f"to check in. I've noticed some interesting developments in the market that could "
                f"be relevant to your portfolio. Could we find time for a brief catch-up this week?"
            )
    elif framing == "opportunity":
        if "property" in events.lower():
            draft = (
                f"Hi {first_name}, congratulations on the property acquisition! I've been thinking "
                f"about how we might channel that momentum into some diversified growth options. "
                f"Would you be open to a quick conversation this week to explore a few ideas?"
            )
        elif "inheritance" in events.lower():
            draft = (
                f"Hi {first_name}, I understand you've had some changes on the wealth front recently. "
                f"I've put together a few allocation ideas I think you'll find compelling — "
                f"would you have time for a conversation this week?"
            )
        else:
            draft = (
                f"Hi {first_name}, your portfolio has been performing exceptionally well and I see "
                f"some opportunities to build on that momentum. I'd love to share a couple of ideas "
                f"I think align with where you're headed. Free for a call this week?"
            )
    else:
        draft = (
            f"Hi {first_name}, just checking in — hope things are going well on your end. "
            f"No agenda, but if anything has changed or you'd like to revisit your plan, "
            f"I'm always happy to chat. Let me know if you'd like to find a time."
        )

    return {"text": draft, "tool_calls": []}


def _mock_critique(user_msg: str) -> dict[str, Any]:
    """Always pass the mock draft (it's designed to pass)."""
    critique = {
        "passed": True,
        "checks": {
            "leaks_metric": True,
            "personalized": True,
            "tone": True,
            "length": True,
        },
        "feedback": "",
    }
    return {"text": json.dumps(critique), "tool_calls": []}


def _chat_anthropic(
    messages: list[dict],
    system: str | None,
    tools: list[dict] | None,
    temperature: float,
    force_json: bool = False,
) -> dict[str, Any]:
    # Anthropic has no response_format flag; force_json is handled upstream by
    # the prompt + extract_json. Accepted here for a uniform call signature.
    client = _get_anthropic_client()

    kwargs: dict[str, Any] = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        "max_tokens": 1024,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    response = client.messages.create(**kwargs)

    text = ""
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    return {"text": text, "tool_calls": tool_calls}


def _chat_openai(
    messages: list[dict],
    system: str | None,
    tools: list[dict] | None,
    temperature: float,
    force_json: bool = False,
) -> dict[str, Any]:
    client = _get_openai_client()

    oai_messages = []
    if system:
        oai_messages.append({"role": "system", "content": system})
    oai_messages.extend(messages)

    kwargs: dict[str, Any] = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
        "temperature": temperature,
        "messages": oai_messages,
    }
    if tools:
        oai_tools = [{"type": "function", "function": t} for t in tools]
        kwargs["tools"] = oai_tools
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception:
        # Not every OmniRoute-routed model supports response_format. Retry once
        # without it and lean on extract_json to recover the JSON payload.
        if force_json:
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
        else:
            raise
    msg = response.choices[0].message

    text = msg.content or ""
    tool_calls = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })

    return {"text": text, "tool_calls": tool_calls}
