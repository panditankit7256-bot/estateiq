"""Optional GenAI layer. If ANTHROPIC_API_KEY is set the structured findings are rewritten / answered by Claude;
otherwise (or on any error) the deterministic templates are used, so the app always works offline."""
from __future__ import annotations
import json
import httpx
from ..core.config import settings

SYSTEM = ("You help facility administrators in India. Use ONLY the numbers and facts in the JSON provided; never invent data. "
          "Write plain, short, practical language. Frame health or environmental statements as indicative decision support, not official measurements.")


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def _call(prompt: str, max_tokens: int = 700) -> str | None:
    if not enabled():
        return None
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=25,
                       headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": settings.anthropic_model, "max_tokens": max_tokens, "system": SYSTEM, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", [])).strip() or None
    except Exception:
        return None


def answer(question: str, facts: dict) -> str | None:
    return _call(f"Question: {question}\n\nFacts (JSON):\n{json.dumps(facts, default=str)[:6000]}\n\nAnswer in at most 120 words, citing the figures.")


def polish(rec: dict) -> dict:
    """Ask the LLM to rewrite the three narrative fields without changing any numbers."""
    out = _call("Rewrite the fields 'detected', 'why' and 'action' of this recommendation in clear, friendly plain English for a non-technical administrator. "
                "Keep every number exactly. Return JSON with exactly those three keys and nothing else.\n" + json.dumps({k: rec[k] for k in ("detected", "why", "action")}), 500)
    if not out:
        return rec
    try:
        data = json.loads(out[out.index("{"): out.rindex("}") + 1])
        if all(isinstance(data.get(k), str) for k in ("detected", "why", "action")):
            return {**rec, **{k: data[k] for k in ("detected", "why", "action")}, "narrative": "llm"}
    except Exception:
        pass
    return rec
