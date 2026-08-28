"""Evaluation metric helpers for LLM-as-judge scoring."""
from __future__ import annotations

import re


def parse_score(text: str) -> float:
    """Parse a 0-1 (or 0-100) score from an LLM judge's output."""
    text = (text or "").strip()
    # First try to find a number in the response
    nums = re.findall(r"(\d+(?:\.\d+)?)", text)
    if not nums:
        return 0.0
    # Prefer first number that looks like a score
    for n in nums:
        val = float(n)
        if val <= 1.0:
            return round(val, 3)
        if val <= 100.0:
            return round(val / 100.0, 3)
    return 0.0


def parse_score_pair(text: str) -> tuple[float, float]:
    """Parse two scores from a generational-judge response (score/10)."""
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if nums:
        num, den = float(nums[-1][0]), float(nums[-1][1])
        return round(num / den, 3), round(num / den, 3)
    return parse_score(text), parse_score(text)
