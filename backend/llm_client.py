"""
llm_client.py
─────────────
Thin async client for Cerebras Cloud (OpenAI-compatible).
Used to generate next-word completions for the suggestion engine.

Cerebras free tier (as of 2026-04): 1M tokens/day, no card.
Sign up: https://cloud.cerebras.ai → API Keys.

Set CEREBRAS_API_KEY in the environment to enable.
"""

import json
import os
import re
from typing import Optional

import httpx

CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
# Valid model IDs (as of 2026-04): llama3.1-8b, gpt-oss-120b,
# qwen-3-235b-a22b-instruct-2507, zai-glm-4.7
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
CEREBRAS_TIMEOUT = float(os.getenv("CEREBRAS_TIMEOUT", "1.5"))  # seconds


SYSTEM_PROMPT = (
    "You are an autocomplete engine for an Islamic scholar writing English prose. "
    "Given the preceding text, the optional voice transcript context, and the "
    "current word the user is typing (the prefix), return up to 8 likely "
    "completions of that current word.\n\n"
    "RULES:\n"
    "- Each completion MUST start with the given prefix (case-insensitive).\n"
    "- Return ONLY single words, lowercase, no punctuation.\n"
    "- Prefer scholarly / Islamic-studies vocabulary when context fits.\n"
    "- Never invent hadith or Quran citations.\n"
    "- Output format: a JSON object {\"completions\": [\"word1\", ...]} and nothing else."
)


def _extract_completions(raw: str, prefix: str) -> list[str]:
    """Parse model output → clean list of completions starting with prefix."""
    prefix_lc = prefix.lower()

    # Try strict JSON first
    try:
        obj = json.loads(raw)
        items = obj.get("completions", []) if isinstance(obj, dict) else []
    except json.JSONDecodeError:
        # Fallback: regex out a JSON array
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        items = []
        if m:
            try:
                items = json.loads(m.group(0))
            except json.JSONDecodeError:
                items = re.findall(r'"([^"]+)"', m.group(0))

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        w = re.sub(r"[^a-zA-Z'-]", "", item).lower().strip("'-")
        if w and w.startswith(prefix_lc) and w not in seen:
            seen.add(w)
            cleaned.append(w)
    return cleaned


async def llm_complete(
    prefix: str,
    prev_text: str,
    mic_transcript: str,
    api_key: str,
) -> list[str]:
    """
    Call Cerebras chat completion. Returns up to 8 candidate words starting
    with `prefix`. Returns [] on any failure (caller should fall back to trie).
    """
    user_msg = (
        f"Preceding text: {prev_text or '(none)'}\n"
        f"Voice transcript context: {mic_transcript or '(none)'}\n"
        f"Current prefix: {prefix}"
    )

    payload = {
        "model": CEREBRAS_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 120,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=CEREBRAS_TIMEOUT) as client:
            r = await client.post(CEREBRAS_API_URL, headers=headers, json=payload)
            if r.status_code >= 400:
                print(
                    f"[llm_client] Cerebras {r.status_code} (model={CEREBRAS_MODEL}): "
                    f"{r.text[:300]}"
                )
                return []
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_completions(content, prefix)
    except Exception as e:
        print(f"[llm_client] Cerebras call failed: {e}")
        return []
