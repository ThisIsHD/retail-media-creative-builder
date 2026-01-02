from __future__ import annotations
from typing import Any, Dict, Literal, Optional


Platform = Literal["instagram_feed", "instagram_story", "facebook_feed", "facebook_story"]


# Platform-specific size constraints
PLATFORM_SPECS: Dict[Platform, Dict[str, Any]] = {
    "instagram_feed": {
        "formats": ["1080x1080", "1080x1350"],
        "max_bytes": 500_000,
        "preferred_mime": "image/jpeg",
        "aspect_ratios": ["1:1", "4:5"],
    },
    "instagram_story": {
        "formats": ["1080x1920"],
        "max_bytes": 500_000,
        "preferred_mime": "image/jpeg",
        "aspect_ratios": ["9:16"],
    },
    "facebook_feed": {
        "formats": ["1200x628", "1080x1080"],
        "max_bytes": 500_000,
        "preferred_mime": "image/jpeg",
        "aspect_ratios": ["1.91:1", "1:1"],
    },
    "facebook_story": {
        "formats": ["1080x1920"],
        "max_bytes": 500_000,
        "preferred_mime": "image/jpeg",
        "aspect_ratios": ["9:16"],
    },
}


def get_platform_specs(platform: Platform) -> Dict[str, Any]:
    """
    Get platform-specific specifications.
    Returns format requirements, size limits, and preferred settings.
    """
    return PLATFORM_SPECS.get(platform, {
        "formats": ["1080x1080"],
        "max_bytes": 500_000,
        "preferred_mime": "image/jpeg",
        "aspect_ratios": ["1:1"],
    })


def validate_platform_format(
    *,
    platform: Platform,
    format: str,
    mime: str,
    bytes: int,
) -> Dict[str, Any]:
    """
    Validate if artifact meets platform requirements.
    Returns validation result with issues if any.
    """
    specs = get_platform_specs(platform)
    issues = []
    
    # Check format
    if format not in specs["formats"]:
        issues.append({
            "code": "FORMAT_MISMATCH",
            "severity": "WARN",
            "message": f"Format {format} not in recommended formats for {platform}",
            "expected": specs["formats"],
        })
    
    # Check file size
    if bytes > specs["max_bytes"]:
        issues.append({
            "code": "SIZE_EXCEEDED",
            "severity": "HARD_FAIL",
            "message": f"File size {bytes} exceeds platform limit {specs['max_bytes']}",
            "current": bytes,
            "limit": specs["max_bytes"],
        })
    
    # Check MIME type
    if mime != specs["preferred_mime"]:
        issues.append({
            "code": "MIME_NOT_PREFERRED",
            "severity": "WARN",
            "message": f"MIME {mime} not preferred for {platform}, recommend {specs['preferred_mime']}",
            "preferred": specs["preferred_mime"],
        })
    
    status = "HARD_FAIL" if any(i["severity"] == "HARD_FAIL" for i in issues) else (
        "WARN" if issues else "PASS"
    )
    
    return {
        "platform": platform,
        "status": status,
        "issues": issues,
        "specs": specs,
    }


def render_platform_metadata(
    *,
    platform: Platform,
    format: str,
) -> Dict[str, Any]:
    """
    Generate platform-specific metadata for rendering.
    Returns metadata dict with platform hints.
    """
    specs = get_platform_specs(platform)
    
    return {
        "platform": platform,
        "format": format,
        "max_bytes": specs["max_bytes"],
        "preferred_mime": specs["preferred_mime"],
        "aspect_ratios": specs["aspect_ratios"],
        "mode": "stub",
        "notes": f"Platform metadata for {platform} ({format})",
    }
