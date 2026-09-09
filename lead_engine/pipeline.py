"""Eight-gate Nexus pipeline: intake → enrich → email? → verify → score → dedupe → CRM → deliver."""

from __future__ import annotations

from typing import Any

from lead_engine.scoring import normalize_prospect

PIPELINE_STAGES = [
    {"id": "intake", "label": "Intake", "hint": "Read prospects"},
    {"id": "enrich", "label": "Enrich", "hint": "Printed contacts only"},
    {"id": "email", "label": "Email?", "hint": "Has address"},
    {"id": "verify", "label": "Verify", "hint": "ZeroBounce-style"},
    {"id": "score", "label": "Score", "hint": "ICP + contact"},
    {"id": "dedupe", "label": "Dedupe", "hint": "Account + email"},
    {"id": "crm", "label": "CRM", "hint": "Upsert lead"},
    {"id": "deliver", "label": "Deliver", "hint": "Client sheet"},
]


def next_status(normalized: dict[str, Any], current: str | None = None) -> str:
    if current in {"delivered", "nurture"}:
        return current
    email_status = normalized.get("email_status")
    if email_status in {"disposable", "invalid"}:
        return "invalid"
    if email_status == "missing":
        return "enriched"
    if normalized.get("is_safe_to_email"):
        return "scored"
    return "verified"


def apply_gates(lead: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(lead)
    if extra:
        for key, value in extra.items():
            if value in (None, ""):
                continue
            if key == "email" and not value:
                continue
            merged[key] = value
    normalized = normalize_prospect(merged)
    status = next_status(normalized, lead.get("status"))
    last_action = "Email failed verify" if status == "invalid" else "Pipeline scored"
    return {
        **lead,
        **normalized,
        "id": lead.get("id"),
        "created_at": lead.get("created_at"),
        "first_touch": lead.get("first_touch"),
        "outreach_draft": lead.get("outreach_draft"),
        "notes": lead.get("notes"),
        "status": status,
        "last_action": last_action,
    }


def pipeline_counts(leads: list[dict[str, Any]]) -> dict[str, int]:
    counts = {stage["id"]: 0 for stage in PIPELINE_STAGES}
    for lead in leads:
        status = lead.get("status")
        if status in {"new"}:
            counts["intake"] += 1
        elif status in {"enriching", "enriched"}:
            counts["enrich"] += 1
            if lead.get("email"):
                counts["email"] += 1
        elif status == "verified":
            counts["verify"] += 1
            counts["email"] += 1
        elif status == "scored":
            counts["score"] += 1
            counts["email"] += 1
            counts["verify"] += 1
            counts["crm"] += 1
        elif status == "delivered":
            counts["deliver"] += 1
            counts["crm"] += 1
            counts["score"] += 1
        elif status == "invalid":
            counts["verify"] += 1
        if lead.get("email"):
            counts["email"] = max(counts["email"], 1)
    counts["dedupe"] = len({(lead.get("email") or lead.get("company") or lead.get("id")) for lead in leads})
    return counts


def draft_outreach(lead: dict[str, Any]) -> str:
    name = (lead.get("first_name") or lead.get("full_name") or "there").split()[0]
    company = lead.get("company") or "your portfolio"
    title = lead.get("title") or "your team"
    return (
        f"{name} — we run recurring exterior and turn work for First Coast {title.lower()} "
        f"books like {company}. Happy to price a 90-day pilot against your current vendor mix. "
        "No invented emails; we only write when the address is marked valid."
    )
