from __future__ import annotations
import os
from dataclasses import dataclass

def _get_env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return v

@dataclass(frozen=True)
class Settings:
    # Mongo
    mongo_uri: str
    mongo_db: str

    # Cerebras
    cerebras_api_key: str | None

    # LangSmith
    langsmith_tracing: bool
    langsmith_endpoint: str | None
    langsmith_api_key: str | None
    langsmith_project: str | None

def load_settings() -> Settings:
    tracing_raw = os.getenv("LANGSMITH_TRACING", "false").lower().strip()
    tracing = tracing_raw in {"1", "true", "yes", "y", "on"}

    return Settings(
        mongo_uri=_get_env("MONGO_URI"),
        mongo_db=os.getenv("MONGO_DB", "tesco_creative_builder"),
        cerebras_api_key=os.getenv("CEREBRAS_API_KEY"),
        langsmith_tracing=tracing,
        langsmith_endpoint=os.getenv("LANGSMITH_ENDPOINT"),
        langsmith_api_key=os.getenv("LANGSMITH_API_KEY"),
        langsmith_project=os.getenv("LANGSMITH_PROJECT"),
    )
