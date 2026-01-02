from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Prompt:
    name: str
    template: str


# Keep prompts short + swappable (you can A/B later).
PROMPTS: Dict[str, Prompt] = {
    "master": Prompt(
        name="master",
        template=(
            "You are the Master Agent for a Retail Media Creative Builder.\n"
            "Goal: produce a concise plan for generating retailer-compliant creatives.\n"
            "Inputs:\n"
            "- User brief: {user_text}\n"
            "- Selected formats: {selected_formats}\n"
            "- Constraints: {constraints}\n"
            "Return JSON with keys: intent, required_assets, notes.\n"
        ),
    ),
    "copy_validator": Prompt(
        name="copy_validator",
        template=(
            "You are a copy compliance assistant for retail media.\n"
            "Check copy against brand/retailer constraints.\n"
            "Copy:\n{copy}\n"
            "Constraints:\n{constraints}\n"
            "Return JSON with keys: decision (PASS|FAIL), findings[], disclaimers[].\n"
        ),
    ),
    "layout_planner": Prompt(
        name="layout_planner",
        template=(
            "Create a platform-safe layout plan for {platform} format {format} ({width}x{height}).\n"
            "Use safe zones and keep it premium and readable.\n"
            "Return JSON that matches the LayoutSpec schema.\n"
        ),
    ),
}


def get_prompt(name: str) -> str:
    if name not in PROMPTS:
        raise KeyError(f"Unknown prompt: {name}")
    return PROMPTS[name].template
