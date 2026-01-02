from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import ValidationError

from src.agents.schemas import CopyOutput
from src.llms.providers.cerebras_client import CerebrasLLM


COPY_VALIDATOR_SYSTEM = """You are a retail-media creative compliance copy validator.
Your job:
1) Detect risky copy claims: price claims, sustainability/charity claims, guarantees, competitor comparisons.
2) Return a structured JSON object exactly matching the provided schema.
3) Be conservative: if uncertain, WARN. If clearly disallowed or unverifiable, HARD_FAIL.

Rules of thumb:
- If the user text includes exact prices, discounts, "best/cheapest", or time-limited offers -> WARN unless disclaimers added.
- If sustainability/eco/charity claims appear -> WARN unless phrased as brand-neutral and non-absolute.
- If guarantees (e.g., "guaranteed results") or competitor comparisons ("better than X") -> HARD_FAIL unless removed.
- Keep copy short, professional, platform-neutral, and suitable for social.
"""

COPY_VALIDATOR_USER_TEMPLATE = """User brief:
{user_text}

Return JSON only.
Schema:
{schema_json}
"""


def _schema_json() -> str:
    # Minimal JSON schema representation (helps LLM adhere)
    example = CopyOutput(
        decision="PASS",
        headline="New look. Same award-winning taste.",
        subhead="Available in major retailers.",
        cta="Shop now",
        caption="Discover the refreshed look with the taste you love.",
        disclaimers=[],
        findings=[],
        notes=["Generated copy is concise and compliant."]
    )
    return example.model_dump_json(indent=2)


def run_copy_validator(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Writes into:
      - outputs.copy_out (structured)
      - pipeline.routing.copy_result
      - compliance_result may remain UNKNOWN here; final decision is in compliance agent.
    """
    user_text = (state.get("user_text") or "").strip()
    if not user_text:
        user_text = "Generate compliant premium creative copy for a retailer campaign."

    llm = CerebrasLLM()

    messages = [
        {"role": "system", "content": COPY_VALIDATOR_SYSTEM},
        {"role": "user", "content": COPY_VALIDATOR_USER_TEMPLATE.format(user_text=user_text, schema_json=_schema_json())},
    ]

    raw = llm.chat(
        model=state.get("session_config", {}).get("copy_model", "llama3.1-8b"),
        messages=messages,
        temperature=0.2,
        max_completion_tokens=700,
    )

    # Try parse JSON strictly
    parsed: Dict[str, Any]
    try:
        parsed = json.loads(raw)
    except Exception:
        # Fallback: attempt to extract JSON substring
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end + 1])
        else:
            parsed = {
                "decision": "WARN",
                "headline": "Compliant creative copy draft",
                "caption": "Generated copy could not be parsed reliably. Please re-prompt.",
                "findings": [
                    {"category": "OTHER", "severity": "MEDIUM", "text_span": "", "reason": "Model output was not valid JSON."}
                ],
                "disclaimers": [],
                "notes": ["Fallback used due to JSON parse failure."]
            }

    # Validate schema
    try:
        out = CopyOutput.model_validate(parsed)
    except ValidationError as ve:
        out = CopyOutput(
            decision="WARN",
            headline="Compliant creative copy draft",
            caption="Output schema validation failed. Please re-prompt.",
            findings=[{
                "category": "OTHER",
                "severity": "MEDIUM",
                "text_span": "",
                "reason": f"Schema validation error: {ve.errors()[0].get('msg', 'unknown')}",
            }],
            notes=["Fallback used due to schema validation failure."]
        )

    # Write to state
    outputs = state.get("outputs", {}) or {}
    outputs.setdefault("copy_out", {})
    outputs["copy_out"] = out.model_dump()

    pipeline = state.get("pipeline", {}) or {}
    pipeline.setdefault("routing", {})
    pipeline["routing"]["copy_result"] = out.decision

    state["outputs"] = outputs
    state["pipeline"] = pipeline
    return state
