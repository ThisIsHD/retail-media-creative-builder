# src/graph/policies.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CompliancePolicy:
    """
    Lightweight policy container.
    Keep this deterministic + versioned.
    """
    name: str
    version: str
    description: str
    rules: Dict[str, Any]


# --- Tesco stub policy (expand later with real Appendix rules) ---
TESCO_APPENDIX_AB_STUB_RULES_V1 = CompliancePolicy(
    name="tesco_appendix_ab_stub_rules_v1",
    version="1.0",
    description="Stub compliance rules for Tesco hackathon (placeholder).",
    rules={
        # Typography
        "typography": {
            "min_font_px": None,  # if None -> WARN in compliance (your current behavior)
            "max_lines_headline": 2,
            "max_lines_subhead": 2,
        },
        # Layout
        "layout": {
            "require_safe_zones": True,
            "safe_zone_min": {"top": 0.05, "bottom": 0.08, "left": 0.04, "right": 0.04},
        },
        # Claims / copy safety (placeholder)
        "claims": {
            "ban_phrases": [
                "guaranteed cure",
                "100% guaranteed",
                "no side effects",
            ],
            "require_disclaimer_if": [
                "limited time",
                "offer ends",
            ],
        },
        # Export constraints
        "export": {
            "max_bytes": 500_000,  # 500 KB soft target
            "allowed_mime": ["image/jpeg", "image/png"],
        },
    },
)


_POLICY_REGISTRY: Dict[str, CompliancePolicy] = {
    TESCO_APPENDIX_AB_STUB_RULES_V1.name: TESCO_APPENDIX_AB_STUB_RULES_V1,
}


def get_policy(name: str) -> CompliancePolicy:
    """
    Fetch a policy by name. Raises KeyError if missing.
    """
    return _POLICY_REGISTRY[name]


def list_policies() -> List[str]:
    return sorted(_POLICY_REGISTRY.keys())


def maybe_get_policy(name: str) -> Optional[CompliancePolicy]:
    return _POLICY_REGISTRY.get(name)
