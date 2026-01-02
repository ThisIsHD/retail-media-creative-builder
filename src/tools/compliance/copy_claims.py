from __future__ import annotations

import re
from typing import Any, Dict, List

from src.tools.compliance.checks import Issue


PRICE_PATTERNS = [
    r"\b\d+(\.\d+)?\s?(?:£|GBP)\b",
    r"\b£\s?\d+(\.\d+)?\b",
    r"\b\d+(\.\d+)?\s?off\b",
    r"\b(save|saving)\s?\d+%?\b",
]

COMPETITOR_PATTERNS = [
    r"\b(best|no\.1|number\s?1|#1)\b",
    r"\b(cheapest|lowest price)\b",
    r"\b(guaranteed|guarantee)\b",
    r"\b(beats?\s+.*price)\b",
]


def detect_copy_issues(copy_text: str) -> List[Issue]:
    issues: List[Issue] = []
    txt = (copy_text or "").strip()

    if not txt:
        issues.append(Issue(code="COPY_EMPTY", severity="WARN", message="Copy text is empty or missing.", field="copy"))
        return issues

    # Price claims
    if any(re.search(p, txt, flags=re.IGNORECASE) for p in PRICE_PATTERNS):
        issues.append(
            Issue(
                code="COPY_PRICE_CLAIM",
                severity="WARN",
                message="Copy appears to contain a price/discount claim. Ensure it matches allowed formats and has required qualifiers.",
                field="copy",
            )
        )

    # Competitor/guarantee claims
    if any(re.search(p, txt, flags=re.IGNORECASE) for p in COMPETITOR_PATTERNS):
        issues.append(
            Issue(
                code="COPY_COMPETITOR_OR_GUARANTEE",
                severity="WARN",
                message="Copy appears to include competitor/guarantee style claims. These often require strict substantiation or are disallowed.",
                field="copy",
            )
        )

    return issues
