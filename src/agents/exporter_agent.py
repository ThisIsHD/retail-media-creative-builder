from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from src.core.hashing import sha256_of_text
from src.core.ids import new_id
from src.core.utils import ensure_list
from src.tools.exporters.optimize_filesize import optimize_filesize_plan


# --- Export constraints (simple defaults; can be extended per platform) ---
DEFAULT_MAX_BYTES_PER_ASSET = 500_000  # 500KB target (hackathon constraint)
DEFAULT_ALLOWED_MIMES = {"image/jpeg", "image/png"}


@dataclass
class ExportResult:
    artifacts: List[Dict[str, Any]]
    export_notes: List[str]
    provider_calls: List[Dict[str, Any]]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_exporter_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 4E: Exporter agent
    - Ensures artifacts are export-ready (size checks + optional optimization plan)
    - Adds export notes into outputs.summary.export_notes
    - Normalizes artifacts structure (adds sha256 if missing, ensures consistent ids)
    """
    outputs = state.get("outputs", {}) or {}
    artifacts = ensure_list(outputs.get("artifacts", []))

    session_config = state.get("session_config", {}) or {}
    ui_context = state.get("ui_context", {}) or {}

    max_bytes = int(session_config.get("max_bytes_per_asset", DEFAULT_MAX_BYTES_PER_ASSET))
    allowed_mimes = set(session_config.get("allowed_mimes", list(DEFAULT_ALLOWED_MIMES)))

    export_notes: List[str] = []
    provider_calls: List[Dict[str, Any]] = []

    if not artifacts:
        export_notes.append("No artifacts produced; nothing to export.")
        outputs.setdefault("summary", {})
        outputs["summary"].setdefault("export_notes", [])
        outputs["summary"]["export_notes"].extend(export_notes)
        state["outputs"] = outputs
        return state

    # Optional: add deterministic export bundle id for this turn
    turn_id = state.get("turn_id") or f"turn_{new_id(12)}"
    state["turn_id"] = turn_id

    for a in artifacts:
        # Normalize artifact fields
        a.setdefault("artifact_id", f"art_{new_id(16)}")
        a.setdefault("type", "image")
        a.setdefault("meta", {})
        a["meta"].setdefault("exported_at", _utcnow_iso())
        a["meta"].setdefault("turn_id", turn_id)

        mime = a.get("mime") or a["meta"].get("mime")
        if mime:
            a["mime"] = mime

        # Add sha256 if absent (best-effort based on uri + ids; real pipeline should hash bytes)
        if not a.get("sha256"):
            fingerprint = f"{a.get('uri','')}\n{a.get('artifact_id','')}\n{a.get('format','')}\n{a.get('mime','')}"
            a["sha256"] = sha256_of_text(fingerprint)

        # Validate mime
        if a.get("mime") and a["mime"] not in allowed_mimes:
            export_notes.append(f"Artifact {a['artifact_id']} mime {a['mime']} not in allowed set; may be rejected.")

        # Enforce bytes budget with an optimization plan (stub-friendly: plan only)
        size_bytes = a.get("bytes")
        if isinstance(size_bytes, int) and size_bytes > max_bytes:
            plan = optimize_filesize_plan(
                current_bytes=size_bytes,
                target_bytes=max_bytes,
                mime=a.get("mime") or "image/jpeg",
                fmt=a.get("format"),
            )
            a["meta"]["optimize_plan"] = plan
            export_notes.append(
                f"Artifact {a['artifact_id']} exceeds {max_bytes} bytes; added optimize_plan (no-op/stub unless renderer applies)."
            )
        elif isinstance(size_bytes, int):
            export_notes.append(f"Artifact {a['artifact_id']} within size budget ({size_bytes} bytes).")

        # Platform naming hints (optional)
        platform = session_config.get("platform") or outputs.get("layout", {}).get("spec", {}).get("platform")
        if platform:
            a["meta"].setdefault("platform", platform)

    # Attach export notes
    outputs.setdefault("summary", {})
    outputs["summary"].setdefault("export_notes", [])
    outputs["summary"]["export_notes"].extend(export_notes)

    # Persist normalized artifacts back
    outputs["artifacts"] = artifacts
    state["outputs"] = outputs

    # Add tracing hooks
    tracing = state.get("tracing", {}) or {}
    tracing.setdefault("provider_calls", [])
    tracing["provider_calls"].extend(provider_calls)
    state["tracing"] = tracing

    # Update pipeline bookkeeping (if present)
    pipeline = state.get("pipeline", {}) or {}
    routing = pipeline.get("routing", {}) or {}
    routing["exporter"] = "OK"
    pipeline["routing"] = routing
    state["pipeline"] = pipeline

    return state
