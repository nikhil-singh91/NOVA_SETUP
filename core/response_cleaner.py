"""Sanitizes model outputs to guarantee no reasoning, think blocks, or metadata leak to user."""

from __future__ import annotations

import re


def clean_model_response(text: str, default_fallback: str = "Hey Boss, I'm here. How can I help?") -> str:
    """Sanitize raw LLM response text.

    Completely strips:
    - <think>...</think> and <thought>...</thought> blocks (including unclosed or prefix cuts)
    - Code-block thoughts (```thought ... ```, ```thinking ... ```)
    - "Here's a thinking process:" and numbered analysis steps
    - Analysis of constraints, mental drafts, and evaluation steps
    - Extra whitespace or leading/trailing markdown fences
    """
    if not text:
        return default_fallback

    # 1. Strip complete <think>...</think> or <thought>...</thought> tags
    text = re.sub(r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", text, flags=re.IGNORECASE)

    # 2. Strip unclosed <think> if it appears at start or end
    text = re.sub(r"^[\s\S]*?</(?:think|thought)>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<(?:think|thought)>[\s\S]*$", "", text, flags=re.IGNORECASE)

    # 3. Strip code-block thoughts: ```thought ... ``` or ```thinking ... ```
    text = re.sub(r"```(?:thought|thinking)[\s\S]*?```", "", text, flags=re.IGNORECASE)

    # 4. Strip "Here's a thinking process:" preludes
    text = re.sub(r"(?i)here(?:'|\x27|’)?s a thinking process:?[\s\S]*?(?=(?:\r?\n){2,}[A-Za-z0-9\"'‘“]|\Z)", "", text)

    # 5. Filter out individual numbered or bulleted reasoning lines
    reasoning_prefixes = (
        "analyze user input", "analyzing user input",
        "identify key constraints", "identifying key constraints", "check constraints", "checking constraints",
        "formulate response", "formulating response", "draft construction", "mental draft",
        "refine response", "refining response", "refine",
        "final check", "final check against constraints",
        "let's analyze", "lets analyze",
        "user says:", "user goal:", "constraints:"
    )

    lines = []
    for line in text.splitlines():
        trimmed = line.strip()
        cleaned_line = re.sub(r"^(?:\d+[\.\)]|\*|-|\+)\s*(?:\*\*)?", "", trimmed).strip().lower()
        if any(cleaned_line.startswith(prefix) for prefix in reasoning_prefixes):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    return cleaned if cleaned else default_fallback
