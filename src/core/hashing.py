from __future__ import annotations
import hashlib


def sha256_of_text(text: str) -> str:
    """Return SHA256 hash of text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_bytes(data: bytes) -> str:
    """Return SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()
